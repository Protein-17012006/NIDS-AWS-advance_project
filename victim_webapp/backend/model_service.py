"""Model loading, caching, and prediction service."""
from __future__ import annotations

import json
import os
import threading
from functools import lru_cache

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

from .config import MODELS_DIR


class ModelService:
    """Lazy-loading model service with thread-safe caching."""

    def __init__(self):
        self._lock = threading.Lock()
        self._models: dict[str, object] = {}
        self._scalers: dict[str, object] = {}
        self._label_encoders: dict[str, object] = {}
        self._feature_names: dict[str, list[str]] = {}
        self._test_data: dict[str, dict] = {}
        self._metadata: dict[str, dict] = {}
        self._model_meta: dict[str, dict] = {}
        self._registry: dict | None = None
        self._settings = {"test_size": 0.2, "random_seed": 42}
        self._cache: dict[str, dict] = {}

    # ─── Registry ──────────────────────────────────────────────

    def get_registry(self) -> dict:
        if self._registry is None:
            path = os.path.join(MODELS_DIR, "registry.json")
            if os.path.exists(path):
                with open(path) as f:
                    self._registry = json.load(f)
            else:
                self._registry = {"datasets": {}, "models": {}}
        return self._registry

    def get_dataset_metadata(self, dataset: str) -> dict:
        if dataset not in self._metadata:
            path = os.path.join(MODELS_DIR, f"{dataset}_metadata.json")
            if os.path.exists(path):
                with open(path) as f:
                    self._metadata[dataset] = json.load(f)
            else:
                raise FileNotFoundError(f"Metadata not found for dataset: {dataset}")
        return self._metadata[dataset]

    def get_model_meta(self, dataset: str, model: str) -> dict:
        key = f"{dataset}_{model}"
        if key not in self._model_meta:
            path = os.path.join(MODELS_DIR, f"{key}_meta.json")
            if os.path.exists(path):
                with open(path) as f:
                    self._model_meta[key] = json.load(f)
            else:
                return {}
        return self._model_meta[key]

    # ─── Lazy Loading ──────────────────────────────────────────

    def _load_model(self, dataset: str, model: str):
        key = f"{dataset}_{model}"
        if key not in self._models:
            with self._lock:
                if key not in self._models:
                    path = os.path.join(MODELS_DIR, f"{key}.joblib")
                    if not os.path.exists(path):
                        raise FileNotFoundError(f"Model not found: {key}")
                    self._models[key] = joblib.load(path)
        return self._models[key]

    def _load_scaler(self, dataset: str, model: str):
        key = f"{dataset}_{model}"
        if key not in self._scalers:
            with self._lock:
                if key not in self._scalers:
                    path = os.path.join(MODELS_DIR, f"{key}_scaler.joblib")
                    if os.path.exists(path):
                        self._scalers[key] = joblib.load(path)
                    else:
                        self._scalers[key] = None
        return self._scalers[key]

    def _load_label_encoder(self, dataset: str):
        if dataset not in self._label_encoders:
            with self._lock:
                if dataset not in self._label_encoders:
                    path = os.path.join(MODELS_DIR, f"{dataset}_label_encoder.joblib")
                    if not os.path.exists(path):
                        raise FileNotFoundError(f"Label encoder not found: {dataset}")
                    self._label_encoders[dataset] = joblib.load(path)
        return self._label_encoders[dataset]

    def _load_feature_names(self, dataset: str) -> list[str]:
        if dataset not in self._feature_names:
            path = os.path.join(MODELS_DIR, f"{dataset}_feature_names.json")
            if not os.path.exists(path):
                raise FileNotFoundError(f"Feature names not found: {dataset}")
            with open(path) as f:
                self._feature_names[dataset] = json.load(f)
        return self._feature_names[dataset]

    def _load_test_data(self, dataset: str) -> dict:
        if dataset not in self._test_data:
            with self._lock:
                if dataset not in self._test_data:
                    path = os.path.join(MODELS_DIR, f"{dataset}_test_sample.joblib")
                    if not os.path.exists(path):
                        raise FileNotFoundError(f"Test data not found: {dataset}")
                    self._test_data[dataset] = joblib.load(path)
        return self._test_data[dataset]

    # ─── Settings ──────────────────────────────────────────────

    def get_settings(self) -> dict:
        return self._settings.copy()

    def update_settings(self, test_size: float, random_seed: int):
        self._settings["test_size"] = test_size
        self._settings["random_seed"] = random_seed
        self._cache.clear()

    def clear_cache(self):
        self._cache.clear()

    # ─── Prediction ────────────────────────────────────────────

    def predict(self, dataset: str, model_name: str) -> dict:
        """Run prediction on precomputed test split. Returns full metrics."""
        cache_key = f"{dataset}_{model_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        clf = self._load_model(dataset, model_name)
        le = self._load_label_encoder(dataset)
        test = self._load_test_data(dataset)
        X_test = test["X"]
        y_test = test["y"]

        # Scale if needed
        scaler = self._load_scaler(dataset, model_name)
        if scaler is not None:
            X_input = scaler.transform(X_test)
        else:
            X_input = X_test.values if hasattr(X_test, "values") else X_test

        # Predict
        y_pred = clf.predict(X_input)

        # Probabilities (if available)
        probabilities = None
        if hasattr(clf, "predict_proba"):
            try:
                proba = clf.predict_proba(X_input)
                probabilities = proba.tolist()
            except Exception:
                pass

        # Metrics
        acc = accuracy_score(y_test, y_pred)
        report = classification_report(
            y_test, y_pred, target_names=le.classes_,
            digits=4, zero_division=0, output_dict=True
        )
        cm = confusion_matrix(y_test, y_pred)
        cm_pct = (cm.astype(float) / cm.sum(axis=1, keepdims=True) * 100)
        cm_pct = np.nan_to_num(cm_pct, nan=0.0)

        # Build per-class metrics
        per_class = {}
        for cls_name in le.classes_:
            if cls_name in report:
                r = report[cls_name]
                per_class[cls_name] = {
                    "precision": round(r["precision"], 4),
                    "recall": round(r["recall"], 4),
                    "f1_score": round(r["f1-score"], 4),
                    "support": int(r["support"]),
                }

        macro = report.get("macro avg", {})
        weighted = report.get("weighted avg", {})

        result = {
            "dataset": dataset,
            "model": model_name,
            "accuracy": round(acc, 4),
            "per_class": per_class,
            "confusion_matrix": cm.tolist(),
            "confusion_matrix_pct": cm_pct.round(2).tolist(),
            "class_names": le.classes_.tolist(),
            "predictions": y_pred.tolist(),
            "true_labels": y_test.tolist() if hasattr(y_test, "tolist") else list(y_test),
            "probabilities": probabilities,
            "macro_avg": {
                "precision": round(macro.get("precision", 0), 4),
                "recall": round(macro.get("recall", 0), 4),
                "f1_score": round(macro.get("f1-score", 0), 4),
                "support": int(macro.get("support", 0)),
            },
            "weighted_avg": {
                "precision": round(weighted.get("precision", 0), 4),
                "recall": round(weighted.get("recall", 0), 4),
                "f1_score": round(weighted.get("f1-score", 0), 4),
                "support": int(weighted.get("support", 0)),
            },
            "sample_count": len(y_test),
        }

        self._cache[cache_key] = result
        return result

    def get_loaded_count(self) -> int:
        return len(self._models)

    def get_available_datasets(self) -> int:
        registry = self.get_registry()
        return len(registry.get("datasets", {}))
