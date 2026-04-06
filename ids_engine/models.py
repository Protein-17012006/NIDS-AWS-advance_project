"""
PyTorch model definitions for the IDS Engine.

Extracted from Meta_Learner_IRM.ipynb — 3 base models + meta-learner.
All base models receive Z ∈ (batch, 30, 64) from FeatureAligner.
"""

import torch
import torch.nn as nn

from .config import LATENT_DIM, WINDOW_SIZE, NUM_CLASSES


# ============================================================
# BASE MODEL 1: CNN + LSTM
# ============================================================

class CNN_LSTM(nn.Module):
    def __init__(self, latent_dim=LATENT_DIM, num_classes=NUM_CLASSES):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(latent_dim, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(0.2),
            nn.Conv1d(128, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(0.2),
            nn.Conv1d(128, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64), nn.ReLU(),
        )
        self.lstm = nn.LSTM(64, 128, num_layers=2, batch_first=True, dropout=0.3)
        self.classifier = nn.Sequential(nn.Dropout(0.3), nn.Linear(128, num_classes))

    def forward(self, z):
        # z: (batch, 30, 64)
        x = z.permute(0, 2, 1)              # (batch, 64, 30)
        x = self.cnn(x).permute(0, 2, 1)    # (batch, 30, 64)
        _, (h_n, _) = self.lstm(x)           # h_n: (2, batch, 128)
        return self.classifier(h_n[-1])      # (batch, num_classes)


# ============================================================
# BASE MODEL 2: TL-BiLSTM (Temporal Attention BiLSTM)
# ============================================================

class TemporalAttention(nn.Module):
    def __init__(self, hidden_dim):
        super().__init__()
        self.attention = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2), nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, lstm_output):
        # lstm_output: (batch, 30, hidden_dim)
        attn_weights = torch.softmax(self.attention(lstm_output), dim=1)
        context = (lstm_output * attn_weights).sum(dim=1)  # (batch, hidden_dim)
        return context, attn_weights.squeeze(-1)


class TL_BiLSTM(nn.Module):
    def __init__(self, latent_dim=LATENT_DIM, hidden_dim=128, num_classes=NUM_CLASSES):
        super().__init__()
        self.bilstm = nn.LSTM(
            latent_dim, hidden_dim // 2, num_layers=2,
            batch_first=True, dropout=0.3, bidirectional=True,
        )
        self.attention = TemporalAttention(hidden_dim)
        self.layer_norm = nn.LayerNorm(hidden_dim)
        self.classifier = nn.Sequential(nn.Dropout(0.3), nn.Linear(hidden_dim, num_classes))

    def forward(self, z):
        # z: (batch, 30, 64)
        lstm_out, _ = self.bilstm(z)             # (batch, 30, 128)
        context, _ = self.attention(lstm_out)     # (batch, 128)
        return self.classifier(self.layer_norm(context))


# ============================================================
# BASE MODEL 3: Transformer
# ============================================================

class TransformerClassifier(nn.Module):
    def __init__(self, d_model=LATENT_DIM, nhead=8, num_layers=4,
                 dim_feedforward=256, num_classes=NUM_CLASSES):
        super().__init__()
        self.pos_enc = nn.Parameter(torch.randn(1, WINDOW_SIZE, d_model) * 0.02)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
            dropout=0.1, batch_first=True, activation='gelu',
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.layer_norm = nn.LayerNorm(d_model)
        self.classifier = nn.Sequential(nn.Dropout(0.3), nn.Linear(d_model, num_classes))

    def forward(self, z):
        # z: (batch, 30, 64)
        x = z + self.pos_enc[:, :z.size(1), :]
        x = self.layer_norm(self.transformer(x))
        return self.classifier(x.mean(dim=1))    # mean-pool → classify


# ============================================================
# WRAPPER: FeatureAligner + Base Model
# ============================================================

class AlignerWithModel(nn.Module):
    """Combines FeatureAligner (domain adaptation) with a base model classifier."""

    def __init__(self, aligner, base_model):
        super().__init__()
        self.aligner = aligner
        self.base_model = base_model

    def forward(self, x, dataset_type='uq'):
        z = self.aligner(x, dataset_type)   # (batch, 30, 64)
        return self.base_model(z)           # (batch, num_classes)

    @torch.no_grad()
    def predict_proba(self, x, dataset_type='uq'):
        self.eval()
        return torch.softmax(self.forward(x, dataset_type), dim=1)


# ============================================================
# META-LEARNER (Dense NN option)
# ============================================================

class DenseMetaLearner(nn.Module):
    def __init__(self, input_dim=15, num_classes=NUM_CLASSES):
        super().__init__()
        self.fc = nn.Linear(input_dim, num_classes)

    def forward(self, x):
        return self.fc(x)



