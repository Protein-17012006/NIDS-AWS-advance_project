"""Pydantic schemas for FastAPI request/response models."""

from pydantic import BaseModel, Field


# ============================================================
# FLOW INGESTION
# ============================================================

class FlowIngestRequest(BaseModel):
    flows: list[dict] = Field(
        ..., description="List of YAF IPFIX flow dicts",
    )
    dataset_type: str = Field(default="yaf", pattern="^(yaf|uq|cic)$")


class FlowIngestResult(BaseModel):
    predicted_class: str
    confidence: float
    severity: str


# ============================================================
# ATTACK CONTROL
# ============================================================

class AttackScheduleRequest(BaseModel):
    """External ground truth registration (used by Attack Simulator UI)."""
    attack_class: str = Field(..., description="UNIFIED_CLASSES label: DDoS, DoS, BruteForce, Infiltration")
    attacker_ip: str = Field(..., description="Attacker source IP")
    start: str = Field(..., description="ISO-8601 UTC start time")
    end: str = Field(..., description="ISO-8601 UTC end time")


# ============================================================
# SYSTEM
# ============================================================

class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    device: str
    uptime_seconds: float
    active_sessions: int


class MetricsResponse(BaseModel):
    total_predictions: int
    class_counts: dict[str, int]
    avg_latency_ms: float
    avg_confidence: float
    alerts_triggered: int
    uptime_seconds: float


# ============================================================
# WEBSOCKET MESSAGES
# ============================================================

class LivePredictionEvent(BaseModel):
    type: str = "prediction"
    data: dict


class AlertEvent(BaseModel):
    type: str = "alert"
    severity: str
    predicted_class: str
    confidence: float
    timestamp: str
    message: str



