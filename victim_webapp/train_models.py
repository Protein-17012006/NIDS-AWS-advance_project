#!/usr/bin/env python3
"""
Train & export all 15 ML models (5 models × 3 datasets) for the victim web app.
Replicates exact preprocessing from Project_1 notebooks.

Usage:
    python train_models.py [--sample N]

Output:
    models/{dataset}_{model}.joblib          — trained model
    models/{dataset}_{model}_scaler.joblib   — StandardScaler (KNN/SVM/LR only)
    models/{dataset}_label_encoder.joblib    — LabelEncoder
    models/{dataset}_feature_names.json      — feature list after selection
    models/{dataset}_class_distribution.json — class sample counts
    models/{dataset}_metadata.json           — dataset info (rows, features, etc.)
"""

import argparse
import json
import os
import sys
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "..", "Project_1", "dataset")
OUTPUT_DIR = os.path.join(BASE_DIR, "models")

DATASETS = {
    "cic2017": {
        "path": os.path.join(DATASET_DIR, "cicids2017_sample_1M_natural_standardized.csv"),
        "reader": "csv",
        "label_col": "Label",
        "mapping": {
            "BENIGN": "BENIGN",
            "DoS Hulk": "DoS",
            "DoS GoldenEye": "DoS",
            "DoS Slowloris": "DoS",
            "DoS Slowhttptest": "DoS",
            "DDoS": "DDoS",
            "FTP-Patator": "BruteForce",
            "SSH-Patator": "BruteForce",
            "Web Attack \u2013 XSS": "BruteForce",
            "Web Attack \u2013 Brute Force": "BruteForce",
            "Web Attack – XSS": "BruteForce",
            "Web Attack – Brute Force": "BruteForce",
            "Heartbleed": "Infiltration",
            "Infiltration": "Infiltration",
        },
        "display": "CIC-IDS-2017",
    },
    "cic2018": {
        "path": os.path.join(DATASET_DIR, "cic2018_balanced_dataset_standardized.parquet"),
        "reader": "parquet",
        "label_col": "Label",
        "mapping": {
            "Benign": "BENIGN",
            "DoS attacks-Hulk": "DoS",
            "DoS attacks-GoldenEye": "DoS",
            "DoS attacks-Slowloris": "DoS",
            "DoS attacks-Slowhttptest": "DoS",
            "DDoS attacks-LOIC-HTTP": "DDoS",
            "DDoS attacks-LOIC-UDP": "DDoS",
            "DDOS attack-HOIC": "DDoS",
            "FTP-BruteForce": "BruteForce",
            "SSH-Bruteforce": "BruteForce",
            "Brute Force -Web": "BruteForce",
            "Brute Force -XSS": "BruteForce",
            "Infilteration": "Infiltration",
        },
        "display": "CSE-CIC-IDS-2018",
    },
    "nf_uq": {
        "path": os.path.join(DATASET_DIR, "nf_uq_balanced_dataset.parquet"),
        "reader": "parquet",
        "label_col": "Label",
        "mapping": {
            "Benign": "BENIGN",
            "DDoS": "DDoS",
            "DoS": "DoS",
            "Brute Force": "BruteForce",
            "Infilteration": "Infiltration",
        },
        "display": "NF-UQ-NIDS-v2",
    },
}

MODELS = {
    "knn": {
        "class": KNeighborsClassifier,
        "params": {"n_neighbors": 5, "weights": "uniform", "metric": "minkowski", "p": 2},
        "needs_scaler": True,
        "display": "K-Nearest Neighbors",
    },
    "logistic_regression": {
        "class": LogisticRegression,
        "params": {"max_iter": 200, "n_jobs": -1, "verbose": 0},
        "needs_scaler": True,
        "display": "Logistic Regression",
    },
    "svm": {
        "class": SGDClassifier,
        "params": {
            "alpha": 0.0001,
            "eta0": 0.1,
            "learning_rate": "adaptive",
            "loss": "modified_huber",
            "max_iter": 1000,
            "penalty": "elasticnet",
        },
        "needs_scaler": True,
        "display": "SVM (SGD)",
    },
    "decision_tree": {
        "class": DecisionTreeClassifier,
        "params": {
            "max_depth": 20,
            "min_samples_split": 10,
            "min_samples_leaf": 4,
            "random_state": 42,
            "class_weight": "balanced",
        },
        "needs_scaler": False,
        "display": "Decision Tree",
    },
    "random_forest": {
        "class": RandomForestClassifier,
        "params": {
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 10,
            "min_samples_leaf": 4,
            "random_state": 42,
            "n_jobs": -1,
            "class_weight": "balanced",
        },
        "needs_scaler": False,
        "display": "Random Forest",
    },
}

DROP_KEYWORDS = [
    "flow id", "flow_id", "source ip", "destination ip",
    "src ip", "dst ip", "timestamp", "source port", "dst port",
]


def load_dataset(cfg, sample_n=None):
    """Load and return raw dataframe."""
    print(f"  Loading {cfg['path']} ...")
    if cfg["reader"] == "csv":
        df = pd.read_csv(cfg["path"])
    else:
        df = pd.read_parquet(cfg["path"])
    if sample_n and len(df) > sample_n:
        df = df.sample(n=sample_n, random_state=42)
        print(f"  Sampled to {sample_n} rows")
    return df


def preprocess(df, label_col, mapping):
    """
    Replicate notebook preprocessing:
    1. Map labels to 5 classes
    2. Drop metadata columns
    3. Handle inf/NaN (median fill)
    4. Variance threshold (0.01)
    5. Z-score outlier removal (|z| < 3)
    6. Correlation filtering (r > 0.95)
    """
    df = df.copy()

    # 1. Label mapping
    df["Label"] = df[label_col].map(mapping)
    df.dropna(subset=["Label"], inplace=True)
    original_rows = len(df)

    # 2. Drop metadata
    cols_to_drop = [
        c for c in df.columns
        if any(k in c.lower() for k in DROP_KEYWORDS)
    ]
    # keep 'Label' safe
    cols_to_drop = [c for c in cols_to_drop if c != "Label"]
    df.drop(columns=cols_to_drop, inplace=True, errors="ignore")

    # 3. Handle inf/NaN
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    for col in numeric_cols:
        if df[col].isnull().sum() > 0:
            df[col].fillna(df[col].median(), inplace=True)

    # 4. Variance threshold
    y = df["Label"]
    X = df.drop("Label", axis=1)
    selector = VarianceThreshold(threshold=0.01)
    X_sel = selector.fit_transform(X)
    selected_features = X.columns[selector.get_support()].tolist()
    df = pd.DataFrame(X_sel, columns=selected_features)
    df["Label"] = y.values

    # 5. Z-score outlier removal (protect minority classes: keep at least 10 per class)
    X_temp = df.drop("Label", axis=1)
    y_temp = df["Label"].reset_index(drop=True)
    X_temp = X_temp.reset_index(drop=True)
    z_scores = np.abs(stats.zscore(X_temp.values, nan_policy="omit"))
    z_outlier = ~(z_scores < 3).all(axis=1)

    # For each class, ensure we keep at least min_keep samples
    min_keep = 10
    keep_mask = ~z_outlier  # start with non-outliers
    for cls in y_temp.unique():
        cls_indices = np.where(y_temp.values == cls)[0]
        cls_kept = keep_mask[cls_indices].sum()
        if cls_kept < min_keep:
            cls_outlier_indices = cls_indices[z_outlier[cls_indices]]
            need = min(min_keep - cls_kept, len(cls_outlier_indices))
            keep_mask[cls_outlier_indices[:need]] = True

    df = X_temp[keep_mask].copy()
    df["Label"] = y_temp[keep_mask].values

    # 6. Correlation filtering
    X_corr = df.drop("Label", axis=1)
    corr_matrix = X_corr.corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape, dtype=bool), k=1))
    to_drop_corr = [c for c in upper.columns if any(upper[c] > 0.95)]
    df.drop(columns=to_drop_corr, inplace=True)

    final_features = [c for c in df.columns if c != "Label"]
    print(f"  Rows: {original_rows} → {len(df)} | Features: {len(final_features)}")
    return df, final_features


def train_and_save(dataset_name, dataset_cfg, sample_n=None):
    """Train all 5 models on one dataset and save artifacts."""
    print(f"\n{'='*60}")
    print(f"DATASET: {dataset_cfg['display']} ({dataset_name})")
    print(f"{'='*60}")

    df_raw = load_dataset(dataset_cfg, sample_n)
    df, feature_names = preprocess(df_raw, dataset_cfg["label_col"], dataset_cfg["mapping"])

    # Encode labels
    le = LabelEncoder()
    df["Label_Encoded"] = le.fit_transform(df["Label"])

    # Save label encoder
    le_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_label_encoder.joblib")
    joblib.dump(le, le_path)

    # Save feature names
    feat_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_feature_names.json")
    with open(feat_path, "w") as f:
        json.dump(feature_names, f)

    # Class distribution
    class_dist = df["Label"].value_counts().to_dict()
    dist_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_class_distribution.json")
    with open(dist_path, "w") as f:
        json.dump(class_dist, f)

    # Dataset metadata
    meta = {
        "name": dataset_cfg["display"],
        "key": dataset_name,
        "total_samples": len(df),
        "num_features": len(feature_names),
        "classes": le.classes_.tolist(),
        "class_distribution": class_dist,
    }
    meta_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    # Split
    X = df[feature_names]
    y = df["Label_Encoded"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # Save test split for web app (sampled to save space)
    test_sample_n = min(5000, len(X_test))
    idx = np.random.RandomState(42).choice(len(X_test), test_sample_n, replace=False)
    X_test_sample = X_test.iloc[idx]
    y_test_sample = y_test.iloc[idx]
    test_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_test_sample.joblib")
    joblib.dump({"X": X_test_sample, "y": y_test_sample}, test_path)

    print(f"  Train: {len(X_train)} | Test: {len(X_test)} | Test sample: {test_sample_n}")

    # Train each model
    for model_name, model_cfg in MODELS.items():
        print(f"\n  --- {model_cfg['display']} ({model_name}) ---")
        t0 = time.time()

        # Scale if needed
        if model_cfg["needs_scaler"]:
            scaler = StandardScaler()
            X_tr = pd.DataFrame(
                scaler.fit_transform(X_train), columns=feature_names, index=X_train.index
            )
            X_te = pd.DataFrame(
                scaler.transform(X_test), columns=feature_names, index=X_test.index
            )
            scaler_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_{model_name}_scaler.joblib")
            joblib.dump(scaler, scaler_path)
        else:
            X_tr, X_te = X_train, X_test

        # Train
        clf = model_cfg["class"](**model_cfg["params"])
        clf.fit(X_tr, y_train)
        elapsed = time.time() - t0

        # Evaluate
        y_pred = clf.predict(X_te)
        acc = accuracy_score(y_test, y_pred)
        report = classification_report(
            y_test, y_pred, target_names=le.classes_, digits=4, zero_division=0, output_dict=True
        )

        print(f"  Accuracy: {acc*100:.2f}% | Time: {elapsed:.1f}s")

        # Save model
        model_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_{model_name}.joblib")
        joblib.dump(clf, model_path)

        # Save model metadata (accuracy, report)
        model_meta = {
            "dataset": dataset_name,
            "model": model_name,
            "display_name": model_cfg["display"],
            "accuracy": round(acc, 4),
            "training_time_sec": round(elapsed, 2),
            "needs_scaler": model_cfg["needs_scaler"],
            "report": report,
        }
        model_meta_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_{model_name}_meta.json")
        with open(model_meta_path, "w") as f:
            json.dump(model_meta, f, indent=2)

    print(f"\n  All models for {dataset_name} saved to {OUTPUT_DIR}/")


def main():
    parser = argparse.ArgumentParser(description="Train & export ML models for victim web app")
    parser.add_argument(
        "--sample", type=int, default=50000,
        help="Max rows per dataset (default: 50000 for EC2-friendly memory)"
    )
    parser.add_argument(
        "--datasets", nargs="+", default=list(DATASETS.keys()),
        help="Which datasets to process"
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Training models with sample_n={args.sample}")
    print(f"Datasets: {args.datasets}")

    for ds_name in args.datasets:
        if ds_name not in DATASETS:
            print(f"Unknown dataset: {ds_name}")
            continue
        train_and_save(ds_name, DATASETS[ds_name], sample_n=args.sample)

    # Save global registry
    registry = {
        "datasets": {k: {"display": v["display"], "key": k} for k, v in DATASETS.items()},
        "models": {k: {"display": v["display"], "key": k, "needs_scaler": v["needs_scaler"]} for k, v in MODELS.items()},
    }
    with open(os.path.join(OUTPUT_DIR, "registry.json"), "w") as f:
        json.dump(registry, f, indent=2)

    print(f"\n{'='*60}")
    print("ALL DONE. Models saved to:", OUTPUT_DIR)
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
