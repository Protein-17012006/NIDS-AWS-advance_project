"""Pydantic schemas for request/response models."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str = ""
    username: str = ""
    message: str = ""


class DatasetInfo(BaseModel):
    key: str
    display: str
    total_samples: int = 0
    num_features: int = 0
    classes: list[str] = []
    class_distribution: dict[str, int] = {}


class ModelInfo(BaseModel):
    key: str
    display: str
    needs_scaler: bool = False


class RegistryResponse(BaseModel):
    datasets: list[DatasetInfo]
    models: list[ModelInfo]


class PredictRequest(BaseModel):
    dataset: str = Field(..., description="Dataset key: cic2017, cic2018, nf_uq")
    model: str = Field(..., description="Model key: knn, logistic_regression, svm, decision_tree, random_forest")


class PerClassMetrics(BaseModel):
    precision: float
    recall: float
    f1_score: float
    support: int


class PredictResponse(BaseModel):
    dataset: str
    model: str
    accuracy: float
    train_accuracy: float | None = None
    per_class: dict[str, PerClassMetrics]
    confusion_matrix: list[list[int]]
    confusion_matrix_pct: list[list[float]]
    class_names: list[str]
    predictions: list[int]
    true_labels: list[int]
    probabilities: list[list[float]] | None = None
    macro_avg: PerClassMetrics
    weighted_avg: PerClassMetrics
    sample_count: int


class SettingsRequest(BaseModel):
    test_size: float = Field(0.2, ge=0.05, le=0.5)
    random_seed: int = Field(42, ge=0, le=99999)


class SettingsResponse(BaseModel):
    test_size: float
    random_seed: int
    message: str = "Settings updated"


class CompareRequest(BaseModel):
    dataset: str
    models: list[str] = Field(default_factory=list, description="If empty, compare all 5 models")


class CompareResponse(BaseModel):
    dataset: str
    results: list[PredictResponse]


class HealthResponse(BaseModel):
    status: str = "ok"
    models_loaded: int = 0
    datasets_available: int = 0


class ErrorResponse(BaseModel):
    detail: str
