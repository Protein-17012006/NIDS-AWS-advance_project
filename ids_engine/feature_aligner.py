"""
Feature Aligner — domain adaptation module.

Maps UQ (47-dim), CIC (78-dim), or YAF (38-dim) features -> shared 64-dim latent space per timestep.

YAF has its own raw feature schema from YAF 3.x IPFIX (--flow-stats). It is NOT mapped
to the UQ schema. The YAFFeatureExtractor learns to project its native feature space
into the shared latent space via domain adaptation (IRM+MMD).
"""

import torch
import torch.nn as nn

from .config import LATENT_DIM


class UQFeatureExtractor(nn.Module):
    """UQ feature dim -> 64-dim latent per timestep."""

    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, LATENT_DIM),
            nn.BatchNorm1d(LATENT_DIM),
            nn.ReLU(),
        )

    def forward(self, x):
        batch, T, D = x.shape
        x_flat = x.reshape(batch * T, D)
        out = self.net(x_flat)
        return out.reshape(batch, T, LATENT_DIM)


class CICFeatureExtractor(nn.Module):
    """CIC feature dim -> 64-dim latent per timestep."""

    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, LATENT_DIM),
            nn.BatchNorm1d(LATENT_DIM),
            nn.ReLU(),
        )

    def forward(self, x):
        batch, T, D = x.shape
        x_flat = x.reshape(batch * T, D)
        out = self.net(x_flat)
        return out.reshape(batch, T, LATENT_DIM)


class YAFFeatureExtractor(nn.Module):
    """
    YAF native feature dim (38) -> 64-dim latent per timestep.

    YAF has its own IPFIX feature schema (protocolIdentifier, octetTotalCount,
    averageInterarrivalTime, etc.) that does NOT match the UQ or CIC schemas.
    This extractor is trained via domain adaptation to project YAF features
    into the same 64-dim latent space as UQ/CIC extractors.
    """

    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, LATENT_DIM),
            nn.BatchNorm1d(LATENT_DIM),
            nn.ReLU(),
        )

    def forward(self, x):
        batch, T, D = x.shape
        x_flat = x.reshape(batch * T, D)
        out = self.net(x_flat)
        return out.reshape(batch, T, LATENT_DIM)


class FeatureAligner(nn.Module):
    """
    Routes input through UQ, CIC, or YAF extractor based on dataset_type.
    Output is always (batch, time_steps, 64) regardless of source domain.
    """

    def __init__(self, uq_input_dim, cic_input_dim, yaf_input_dim):
        super().__init__()
        self.uq_extractor = UQFeatureExtractor(uq_input_dim)
        self.cic_extractor = CICFeatureExtractor(cic_input_dim)
        self.yaf_extractor = YAFFeatureExtractor(yaf_input_dim)

    def forward(self, x, dataset_type='uq'):
        if dataset_type == 'yaf':
            return self.yaf_extractor(x)
        elif dataset_type == 'cic':
            return self.cic_extractor(x)
        else:
            return self.uq_extractor(x)
