"""
ML Prediction Web App — FastAPI Backend
Serves 5 sklearn models × 3 datasets with full evaluation metrics.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .model_service import ModelService
from .schemas import (
    CompareRequest,
    CompareResponse,
    DatasetInfo,
    ErrorResponse,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    ModelInfo,
    PredictRequest,
    PredictResponse,
    RegistryResponse,
    SettingsRequest,
    SettingsResponse,
)

svc = ModelService()
ws_clients: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload registry
    svc.get_registry()
    yield


app = FastAPI(
    title="NIDS ML Prediction Platform",
    description="Network Intrusion Detection — 5 Models × 3 Datasets",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Auth ──────────────────────────────────────────────────────

# Hardcoded demo credentials
_VALID_USERS = {
    "admin": "admin123",
    "analyst": "analyst2024",
    "demo": "demo",
}


@app.post("/api/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    if _VALID_USERS.get(req.username) == req.password:
        import hashlib, time as _t
        token = hashlib.sha256(f"{req.username}:{_t.time()}".encode()).hexdigest()
        return LoginResponse(
            success=True,
            token=token,
            username=req.username,
            message="Login successful",
        )
    raise HTTPException(
        status_code=401,
        detail="Invalid username or password",
    )


# ─── Health ────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        models_loaded=svc.get_loaded_count(),
        datasets_available=svc.get_available_datasets(),
    )


# ─── GET — Datasets & Models ──────────────────────────────────

@app.get("/api/datasets", response_model=list[DatasetInfo])
async def list_datasets():
    registry = svc.get_registry()
    result = []
    for key, info in registry.get("datasets", {}).items():
        try:
            meta = svc.get_dataset_metadata(key)
            result.append(DatasetInfo(
                key=key,
                display=meta.get("name", info.get("display", key)),
                total_samples=meta.get("total_samples", 0),
                num_features=meta.get("num_features", 0),
                classes=meta.get("classes", []),
                class_distribution=meta.get("class_distribution", {}),
            ))
        except FileNotFoundError:
            result.append(DatasetInfo(key=key, display=info.get("display", key)))
    return result


@app.get("/api/models", response_model=list[ModelInfo])
async def list_models():
    registry = svc.get_registry()
    return [
        ModelInfo(key=k, display=v.get("display", k), needs_scaler=v.get("needs_scaler", False))
        for k, v in registry.get("models", {}).items()
    ]


# ─── POST — Predict ───────────────────────────────────────────

@app.post("/api/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    registry = svc.get_registry()
    if req.dataset not in registry.get("datasets", {}):
        raise HTTPException(status_code=400, detail=f"Unknown dataset: {req.dataset}")
    if req.model not in registry.get("models", {}):
        raise HTTPException(status_code=400, detail=f"Unknown model: {req.model}")

    try:
        result = svc.predict(req.dataset, req.model)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

    # Broadcast via WebSocket
    event = {
        "type": "prediction_complete",
        "dataset": req.dataset,
        "model": req.model,
        "accuracy": result["accuracy"],
    }
    for ws in list(ws_clients):
        try:
            await ws.send_json(event)
        except Exception:
            ws_clients.discard(ws)

    return PredictResponse(**result)


# ─── POST — Compare all models ────────────────────────────────

@app.post("/api/compare", response_model=CompareResponse)
async def compare(req: CompareRequest):
    registry = svc.get_registry()
    if req.dataset not in registry.get("datasets", {}):
        raise HTTPException(status_code=400, detail=f"Unknown dataset: {req.dataset}")

    models_to_run = req.models if req.models else list(registry.get("models", {}).keys())
    results = []
    for model_name in models_to_run:
        if model_name not in registry.get("models", {}):
            continue
        try:
            r = svc.predict(req.dataset, model_name)
            results.append(PredictResponse(**r))
        except Exception:
            continue

    return CompareResponse(dataset=req.dataset, results=results)


# ─── PUT — Settings ───────────────────────────────────────────

@app.put("/api/settings", response_model=SettingsResponse)
async def update_settings(req: SettingsRequest):
    svc.update_settings(req.test_size, req.random_seed)
    return SettingsResponse(
        test_size=req.test_size,
        random_seed=req.random_seed,
        message="Settings updated. Cache cleared.",
    )


@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings():
    s = svc.get_settings()
    return SettingsResponse(**s, message="Current settings")


# ─── DELETE — Cache ────────────────────────────────────────────

@app.delete("/api/cache")
async def clear_cache():
    svc.clear_cache()
    return {"message": "Prediction cache cleared"}


# ─── WebSocket — Live Updates ──────────────────────────────────

@app.websocket("/ws/predictions")
async def websocket_predictions(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.discard(ws)
