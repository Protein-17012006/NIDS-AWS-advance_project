"""
Inference Engine — orchestrates the full ML prediction pipeline.

Loads trained models, accepts windowed features, returns predictions.
Pipeline: FeatureAligner -> 3 base models -> Meta-learner -> class prediction

ML is the PRIMARY and ONLY detection mechanism. No rule-based fallback.
Training and retraining are done locally, not on the cloud instance.
"""

import os
import logging
import time
import numpy as np
import torch
import joblib

from .config import (
    LATENT_DIM, NUM_CLASSES, UNIFIED_CLASSES,
    UQ_INPUT_DIM, CIC_INPUT_DIM, YAF_INPUT_DIM,
    BASE_MODEL_NAMES, MODEL_FILES, META_LEARNER_FILE,
    SCALER_UQ_FILE, SCALER_YAF_FILE,
    MODEL_DIR, INFERENCE_BATCH_SIZE, DEFAULT_DATASET_TYPE,
    S3_MODEL_BUCKET, S3_MODEL_PREFIX,
    DEFAULT_TEMPERATURE,
)
from .feature_aligner import FeatureAligner, YAFFeatureExtractor
from .models import (
    CNN_LSTM, TL_BiLSTM, TransformerClassifier,
    AlignerWithModel, DenseMetaLearner,
)

logger = logging.getLogger(__name__)


class InferenceEngine:
    """
    Full ML inference pipeline: windows -> base model probs -> meta-learner -> prediction.

    Usage:
        engine = InferenceEngine(model_dir='/path/to/Model_IRM')
        result = engine.predict(windows, dataset_type='yaf')
    """

    def __init__(self, model_dir: str | None = None, device: str | None = None):
        self.model_dir = model_dir or MODEL_DIR
        self.device = torch.device(
            device if device else ('cuda' if torch.cuda.is_available() else 'cpu')
        )
        self.models: dict[str, AlignerWithModel] = {}
        self.meta_learner = None
        self.meta_type = 'lr'
        self.scalers: dict[str, object] = {}  # per-domain scalers: 'uq', 'yaf'
        self._loaded = False

        self.temperature = DEFAULT_TEMPERATURE

        logger.info("InferenceEngine created, device=%s, model_dir=%s",
                     self.device, self.model_dir)

    def load_models(self):
        """Load all model weights from disk (or download from S3 first)."""
        if self._loaded:
            return

        self._ensure_models_local()

        base_models = {
            'cnn_lstm': CNN_LSTM(),
            'tl_bilstm': TL_BiLSTM(),
            'transformer': TransformerClassifier(),
        }

        for name in BASE_MODEL_NAMES:
            path = os.path.join(self.model_dir, MODEL_FILES[name])
            aligner = FeatureAligner(UQ_INPUT_DIM, CIC_INPUT_DIM, YAF_INPUT_DIM)
            model = AlignerWithModel(aligner, base_models[name])

            state = torch.load(path, map_location=self.device, weights_only=False)
            missing, unexpected = model.load_state_dict(state, strict=False)
            if missing:
                logger.info("Missing keys for %s (expected for new YAF extractor): %s",
                            name, missing)

            model.to(self.device)
            model.eval()
            self.models[name] = model
            logger.info("Loaded base model: %s from %s", name, path)

        # Load meta-learner
        meta_path = os.path.join(self.model_dir, META_LEARNER_FILE)
        if meta_path.endswith('.pkl'):
            self.meta_learner = joblib.load(meta_path)
            self.meta_type = 'lr'
            logger.info("Loaded meta-learner (LogisticRegression) from %s", meta_path)
        else:
            self.meta_learner = DenseMetaLearner(
                input_dim=len(BASE_MODEL_NAMES) * NUM_CLASSES,
                num_classes=NUM_CLASSES,
            )
            self.meta_learner.load_state_dict(
                torch.load(meta_path, map_location=self.device, weights_only=False)
            )
            self.meta_learner.to(self.device)
            self.meta_learner.eval()
            self.meta_type = 'nn'
            logger.info("Loaded meta-learner (DenseNN) from %s", meta_path)

        # Load per-domain scalers
        for dataset_type, scaler_file in [('uq', SCALER_UQ_FILE), ('yaf', SCALER_YAF_FILE)]:
            scaler_path = os.path.join(self.model_dir, scaler_file)
            if os.path.exists(scaler_path):
                self.scalers[dataset_type] = joblib.load(scaler_path)
                logger.info("Loaded scaler for %s from %s", dataset_type, scaler_path)
            else:
                logger.warning("No scaler found for %s at %s", dataset_type, scaler_path)

        self._loaded = True
        logger.info("All models loaded successfully")

    def _ensure_models_local(self):
        """Download models from S3 if not present locally."""
        if not S3_MODEL_BUCKET:
            return

        import boto3
        s3 = boto3.client('s3')

        needed = list(MODEL_FILES.values()) + [META_LEARNER_FILE, SCALER_UQ_FILE, SCALER_YAF_FILE]
        for fname in needed:
            local_path = os.path.join(self.model_dir, fname)
            if os.path.exists(local_path):
                continue
            s3_key = S3_MODEL_PREFIX + fname
            logger.info("Downloading %s from s3://%s/%s", fname, S3_MODEL_BUCKET, s3_key)
            os.makedirs(self.model_dir, exist_ok=True)
            try:
                s3.download_file(S3_MODEL_BUCKET, s3_key, local_path)
            except s3.exceptions.ClientError:
                logger.warning("S3 file not found: %s — skipping", s3_key)

    def _get_scaler(self, dataset_type: str):
        """Get the appropriate scaler for the dataset type."""
        return self.scalers.get(dataset_type)

    @torch.no_grad()
    def _predict_proba_base(self, windows: np.ndarray,
                             dataset_type: str,
                             model_name: str) -> np.ndarray:
        """Get softmax probabilities from one base model."""
        model = self.models[model_name]
        model.eval()

        all_probs = []
        n = len(windows)
        for start in range(0, n, INFERENCE_BATCH_SIZE):
            batch = torch.FloatTensor(
                windows[start:start + INFERENCE_BATCH_SIZE]
            ).to(self.device)
            probs = torch.softmax(model(batch, dataset_type), dim=1)
            all_probs.append(probs.cpu().numpy())

        return np.vstack(all_probs)

    def predict(self, windows: np.ndarray,
                dataset_type: str = DEFAULT_DATASET_TYPE) -> dict:
        """
        Full ML pipeline: windows -> 3 base models -> meta-learner -> predictions.

        Args:
            windows: (N, 30, feature_dim) feature windows (raw or pre-scaled)
            dataset_type: 'yaf', 'uq', or 'cic'

        Returns:
            dict with predictions, class_names, probabilities, confidence, latency_ms
        """
        if not self._loaded:
            self.load_models()

        t0 = time.time()

        # Step 0: apply per-domain StandardScaler if available
        scaler = self._get_scaler(dataset_type)
        if scaler is not None:
            n, t, f = windows.shape
            flat = windows.reshape(-1, f)
            flat = scaler.transform(flat).astype(np.float32)
            windows = flat.reshape(n, t, f)

        # Step 1: base model probabilities
        probs_list = []
        for name in BASE_MODEL_NAMES:
            probs = self._predict_proba_base(windows, dataset_type, name)
            probs_list.append(probs)

        # Step 2: stack -> meta-features (N, 15)
        x_meta = np.hstack(probs_list)

        # Step 3: meta-learner prediction
        if self.meta_type == 'lr':
            preds = self.meta_learner.predict(x_meta)
            if hasattr(self.meta_learner, 'predict_proba'):
                meta_probs = self.meta_learner.predict_proba(x_meta)
            else:
                meta_probs = x_meta[:, :NUM_CLASSES]
        else:
            x_t = torch.FloatTensor(x_meta).to(self.device)
            logits = self.meta_learner(x_t)
            logits = logits / self.temperature
            meta_probs = torch.softmax(logits, dim=1).cpu().numpy()
            preds = logits.argmax(1).cpu().numpy()

        class_names = [UNIFIED_CLASSES[int(p)] for p in preds]
        confidence = np.max(meta_probs, axis=1)

        latency_ms = (time.time() - t0) * 1000

        return {
            'predictions': preds,
            'class_names': class_names,
            'probabilities': meta_probs,
            'confidence': confidence,
            'latency_ms': latency_ms,
        }


