"""Configuration for the ML web app backend."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "..", "models")

DATASETS = ["cic2017", "cic2018", "nf_uq"]
MODELS = ["knn", "logistic_regression", "svm", "decision_tree", "random_forest"]

UNIFIED_CLASSES = ["BENIGN", "BruteForce", "DDoS", "DoS", "Infiltration"]
