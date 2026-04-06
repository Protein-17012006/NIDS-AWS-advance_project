"""
Phase 1: Feature Alignment / Domain Adaptation
Đồng nhất không gian đặc trưng từ UQ (49 features) và CIC-2017 (78 features)
về không gian ẩn chung 64 chiều, tạo chuỗi thời gian cho các model deep learning.
"""

import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler, LabelEncoder
from torch.utils.data import Dataset, DataLoader

# ============================================================
# CONSTANTS
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UQ_DATA_PATH = os.path.join(BASE_DIR, "Dataset", "nf_uq_balanced_dataset_v3.parquet")
CIC_DATA_PATH = os.path.join(BASE_DIR, "Dataset", "cic2017_balanced_dataset.parquet")

UNIFIED_CLASSES = ['Benign', 'BruteForce', 'DDoS', 'DoS', 'Infiltration']

WINDOW_SIZE = 30
STRIDE = 10
LATENT_DIM = 64
NUM_CLASSES = 5

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# --- UQ: Cột dùng để group session ---
UQ_SESSION_COLS = ['L4_SRC_PORT', 'L4_DST_PORT']

# --- CIC: Cột dùng để group session ---
CIC_SESSION_COLS = ['Source Port', 'Destination Port']

# --- UQ: Columns to DROP (metadata, non-numeric, labels) ---
UQ_DROP_COLS = ['IPV4_SRC_ADDR', 'IPV4_DST_ADDR', 'Label',
                'FLOW_START_MILLISECONDS', 'FLOW_END_MILLISECONDS']

# --- CIC: Columns to DROP ---
CIC_DROP_COLS = ['Flow ID', 'Source IP', 'Destination IP', 'Timestamp', 'Label']

# --- Label Mapping ---
CIC_LABEL_MAP = {
    'BENIGN': 'Benign',
    'DoS Hulk': 'DoS',
    'DoS GoldenEye': 'DoS',
    'DoS slowloris': 'DoS',
    'DoS Slowhttptest': 'DoS',
    'DDoS': 'DDoS',
    'FTP-Patator': 'BruteForce',
    'SSH-Patator': 'BruteForce',
    'Web Attack  Brute Force': 'BruteForce',
    'Web Attack  Brute Force': 'BruteForce',
    'Web Attack  XSS': 'BruteForce',
    'Web Attack  XSS': 'BruteForce',
    'Infiltration': 'Infiltration',
}

# Labels to DROP from CIC 2017 (not in unified 5-class scheme)
CIC_DROP_LABELS = ['PortScan', 'Bot', 'Heartbleed',
                   'Web Attack  Sql Injection', 'Web Attack  Sql Injection']

UQ_LABEL_MAP = {
    'Benign': 'Benign',
    'Bruteforce': 'BruteForce',
    'Ddos': 'DDoS',
    'Dos': 'DoS',
    'Infilteration': 'Infiltration',
}

# ============================================================
# DATA LOADING
# ============================================================

def load_uq_data(path=None):
    """Load NF-UQ dataset, map labels, return features DataFrame + labels Series."""
    if path is None:
        path = UQ_DATA_PATH
    df = pd.read_parquet(path)

    # Map labels
    df['Label'] = df['Label'].map(UQ_LABEL_MAP)
    df = df.dropna(subset=['Label'])

    labels = df['Label'].copy()

    # Extract session columns before dropping
    session_keys = df[UQ_SESSION_COLS].copy()

    # Drop non-feature columns
    features = df.drop(columns=[c for c in UQ_DROP_COLS if c in df.columns], errors='ignore')
    # Keep session cols in features for grouping, will drop later
    feature_cols = [c for c in features.columns if c not in UQ_SESSION_COLS]

    return features, labels, session_keys, feature_cols


def load_cic_data(path=None):
    """Load CIC-2017 dataset, map labels, drop unwanted attack types."""
    if path is None:
        path = CIC_DATA_PATH
    df = pd.read_parquet(path)

    # Drop unwanted labels
    df = df[~df['Label'].isin(CIC_DROP_LABELS)].copy()

    # Map labels
    df['Label'] = df['Label'].map(CIC_LABEL_MAP)
    df = df.dropna(subset=['Label'])

    labels = df['Label'].copy()

    # Extract session columns
    session_keys = df[CIC_SESSION_COLS].copy()
    session_keys.columns = UQ_SESSION_COLS  # Rename to unified names

    # Drop non-feature columns
    features = df.drop(columns=[c for c in CIC_DROP_COLS if c in df.columns], errors='ignore')
    feature_cols = [c for c in features.columns if c not in CIC_SESSION_COLS]

    return features, labels, session_keys, feature_cols


# ============================================================
# TIME SERIES CREATION (Session Grouping + Sliding Window)
# ============================================================

def create_sessions_and_windows(features_df, labels_series, session_keys_df,
                                 feature_cols, window_size=WINDOW_SIZE,
                                 stride=STRIDE):
    """
    Group flows by (SRC_PORT, DST_PORT) to form sessions,
    then create sliding windows of fixed size.

    Returns:
        windows: np.ndarray (N_windows, window_size, n_features)
        window_labels: np.ndarray (N_windows,) — majority label per window
    """
    # Prepare numeric features only
    X = features_df[feature_cols].values.astype(np.float32)
    y = labels_series.values
    keys = session_keys_df.values

    # Replace inf/nan
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # Group by session keys
    # Create a composite key for grouping
    session_ids = pd.Series(
        [f"{int(k[0])}_{int(k[1])}" for k in keys],
        index=features_df.index
    )

    windows_list = []
    labels_list = []

    for _, group_idx in session_ids.groupby(session_ids).groups.items():
        group_idx_sorted = sorted(group_idx)
        session_X = X[features_df.index.get_indexer(group_idx_sorted)]
        session_y = y[features_df.index.get_indexer(group_idx_sorted)]

        n_flows = len(session_X)

        if n_flows < window_size:
            # Pad with zeros
            padded = np.zeros((window_size, session_X.shape[1]), dtype=np.float32)
            padded[:n_flows] = session_X
            windows_list.append(padded)
            # Majority label
            vals, counts = np.unique(session_y, return_counts=True)
            labels_list.append(vals[np.argmax(counts)])
        else:
            # Sliding window
            for start in range(0, n_flows - window_size + 1, stride):
                window = session_X[start:start + window_size]
                window_y = session_y[start:start + window_size]
                windows_list.append(window)
                vals, counts = np.unique(window_y, return_counts=True)
                labels_list.append(vals[np.argmax(counts)])

    windows = np.array(windows_list, dtype=np.float32)
    window_labels = np.array(labels_list)

    return windows, window_labels


# ============================================================
# LABEL ENCODING
# ============================================================

def encode_labels(labels, classes=None):
    """Encode string labels to integers using UNIFIED_CLASSES order."""
    if classes is None:
        classes = UNIFIED_CLASSES
    le = LabelEncoder()
    le.classes_ = np.array(classes)
    encoded = le.transform(labels)
    return encoded, le


# ============================================================
# FEATURE SCALING
# ============================================================

def fit_scaler(windows):
    """Fit StandardScaler on flattened windows. Returns scaler."""
    n, t, f = windows.shape
    flat = windows.reshape(-1, f)
    scaler = StandardScaler()
    scaler.fit(flat)
    return scaler


def apply_scaler(windows, scaler):
    """Apply fitted scaler to windows."""
    n, t, f = windows.shape
    flat = windows.reshape(-1, f)
    scaled = scaler.transform(flat).astype(np.float32)
    return scaled.reshape(n, t, f)


# ============================================================
# PYTORCH FEATURE EXTRACTORS
# ============================================================

class UQFeatureExtractor(nn.Module):
    """Chuyển đổi từ UQ feature dim → 64 chiều (per timestep)."""

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
        # x: (batch, time_steps, input_dim)
        batch, T, D = x.shape
        x_flat = x.reshape(batch * T, D)
        out = self.net(x_flat)
        return out.reshape(batch, T, LATENT_DIM)


class CICFeatureExtractor(nn.Module):
    """Chuyển đổi từ CIC 78 features → 64 chiều (per timestep)."""

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
        # x: (batch, time_steps, input_dim)
        batch, T, D = x.shape
        x_flat = x.reshape(batch * T, D)
        out = self.net(x_flat)
        return out.reshape(batch, T, LATENT_DIM)


class FeatureAligner(nn.Module):
    """
    Bộ chuyển đổi: Nhận dữ liệu thô từ UQ hoặc CIC,
    ánh xạ về không gian ẩn chung Z (batch, 30, 64).
    """

    def __init__(self, uq_input_dim, cic_input_dim):
        super().__init__()
        self.uq_extractor = UQFeatureExtractor(uq_input_dim)
        self.cic_extractor = CICFeatureExtractor(cic_input_dim)

    def forward(self, x, dataset_type='uq'):
        """
        Args:
            x: (batch, time_steps, feature_dim) — raw scaled features
            dataset_type: 'uq' or 'cic'
        Returns:
            Z: (batch, time_steps, 64)
        """
        if dataset_type == 'uq':
            return self.uq_extractor(x)
        else:
            return self.cic_extractor(x)


# ============================================================
# PYTORCH DATASET
# ============================================================

class TimeSeriesDataset(Dataset):
    """PyTorch Dataset for windowed time-series data."""

    def __init__(self, windows, labels, dataset_type='uq'):
        self.windows = torch.FloatTensor(windows)
        self.labels = torch.LongTensor(labels)
        self.dataset_type = dataset_type

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.windows[idx], self.labels[idx], self.dataset_type


# ============================================================
# FULL PIPELINE: Load → Session → Window → Scale → Encode
# ============================================================

def prepare_dataset(dataset_type='uq', scaler=None):
    """
    Complete pipeline: load data, create sessions/windows, scale, encode labels.

    Args:
        dataset_type: 'uq' or 'cic'
        scaler: pre-fitted scaler (optional, for val/test)

    Returns:
        windows_scaled: np.ndarray (N, 30, feature_dim)
        labels_encoded: np.ndarray (N,)
        scaler: fitted StandardScaler
        label_encoder: fitted LabelEncoder
        n_features: int — number of input features
    """
    if dataset_type == 'uq':
        features, labels, session_keys, feature_cols = load_uq_data()
    else:
        features, labels, session_keys, feature_cols = load_cic_data()

    print(f"[{dataset_type.upper()}] Loaded {len(features)} flows, "
          f"{len(feature_cols)} features")
    print(f"[{dataset_type.upper()}] Label distribution:")
    print(labels.value_counts().to_string())

    # Create sessions and windows
    windows, window_labels = create_sessions_and_windows(
        features, labels, session_keys, feature_cols
    )
    print(f"[{dataset_type.upper()}] Created {len(windows)} windows "
          f"of shape {windows.shape}")

    # Scale
    if scaler is None:
        scaler = fit_scaler(windows)
    windows_scaled = apply_scaler(windows, scaler)

    # Encode labels
    labels_encoded, le = encode_labels(window_labels)

    n_features = windows_scaled.shape[2]
    print(f"[{dataset_type.upper()}] Feature dim: {n_features}, "
          f"Latent target: {LATENT_DIM}")

    return windows_scaled, labels_encoded, scaler, le, n_features


def prepare_combined_dataset():
    """
    Load and prepare both UQ and CIC datasets.
    Returns combined windows (still separate feature dims),
    encoded labels, scalers, and feature dims.
    """
    # Prepare UQ
    uq_windows, uq_labels, uq_scaler, le, uq_n_feat = prepare_dataset('uq')

    # Prepare CIC
    cic_windows, cic_labels, cic_scaler, _, cic_n_feat = prepare_dataset('cic')

    # Track dataset origin
    uq_types = np.array(['uq'] * len(uq_labels))
    cic_types = np.array(['cic'] * len(cic_labels))

    print(f"\n=== Combined Dataset ===")
    print(f"UQ: {len(uq_windows)} windows, {uq_n_feat} features")
    print(f"CIC: {len(cic_windows)} windows, {cic_n_feat} features")
    print(f"Total: {len(uq_windows) + len(cic_windows)} windows")

    return {
        'uq': {
            'windows': uq_windows,
            'labels': uq_labels,
            'scaler': uq_scaler,
            'n_features': uq_n_feat,
            'dataset_type': uq_types,
        },
        'cic': {
            'windows': cic_windows,
            'labels': cic_labels,
            'scaler': cic_scaler,
            'n_features': cic_n_feat,
            'dataset_type': cic_types,
        },
        'label_encoder': le,
        'classes': UNIFIED_CLASSES,
        'n_classes': NUM_CLASSES,
    }


# ============================================================
# UTILITY: Create DataLoaders
# ============================================================

def create_dataloaders(windows, labels, dataset_type='uq',
                       batch_size=256, shuffle=True):
    """Create PyTorch DataLoader from numpy arrays."""
    ds = TimeSeriesDataset(windows, labels, dataset_type)
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle,
                      num_workers=0, pin_memory=True)


# ============================================================
# MAIN (test)
# ============================================================

if __name__ == '__main__':
    print("Testing feature alignment pipeline...")
    print(f"Device: {DEVICE}")
    print()

    data = prepare_combined_dataset()

    # Test FeatureAligner
    aligner = FeatureAligner(
        uq_input_dim=data['uq']['n_features'],
        cic_input_dim=data['cic']['n_features']
    ).to(DEVICE)

    # Test UQ forward pass
    sample_uq = torch.FloatTensor(data['uq']['windows'][:4]).to(DEVICE)
    z_uq = aligner(sample_uq, 'uq')
    print(f"UQ input: {sample_uq.shape} → Z: {z_uq.shape}")

    # Test CIC forward pass
    sample_cic = torch.FloatTensor(data['cic']['windows'][:4]).to(DEVICE)
    z_cic = aligner(sample_cic, 'cic')
    print(f"CIC input: {sample_cic.shape} → Z: {z_cic.shape}")

    assert z_uq.shape == (4, WINDOW_SIZE, LATENT_DIM)
    assert z_cic.shape == (4, WINDOW_SIZE, LATENT_DIM)
    print("\n✓ All shapes correct: (batch, 30, 64)")
