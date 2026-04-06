"""
FastAPI server for the IDS Engine — ML-first architecture.

Endpoints:
- POST /flows — ingest YAF IPFIX flows → ML prediction
- WebSocket /ws/live — real-time prediction stream
- GET /attack/schedule — current attack schedule
- POST /attack/schedule — register ground truth
- GET /evaluation/detection-report — SOC-style detection metrics
- POST /evaluation/reset — clear evaluation data
- GET /health — health check
- GET /metrics — prediction counts and latency
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from collections import defaultdict

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import (
    UNIFIED_CLASSES, SEVERITY_MAP,
    ATTACKER_IP, AWS_REGION,
)
from .inference import InferenceEngine
from .labeler import GroundTruthLabeler
from .feature_pipeline import FlowWindowBuffer, parse_yaf_flow, extract_ports
from .evaluation import EvaluationTracker
from .schemas import (
    FlowIngestRequest, FlowIngestResult,
    AttackScheduleRequest,
    HealthResponse, MetricsResponse,
    LivePredictionEvent, AlertEvent,
)
from .auto_response import AutoResponseManager

logger = logging.getLogger(__name__)

# ============================================================
# GLOBAL STATE
# ============================================================
engine = InferenceEngine()
labeler = GroundTruthLabeler()
start_time = time.time()

# Metrics counters
prediction_counts: dict[str, int] = defaultdict(int)
total_predictions = 0
total_latency_ms = 0.0
total_confidence = 0.0
alert_count = 0

# Flow window buffer for /flows endpoint
flow_buffer = FlowWindowBuffer()

# Evaluation tracker (ground truth alignment)
eval_tracker = EvaluationTracker()

# WebSocket connections
ws_clients: set[WebSocket] = set()

# Auto-response manager
auto_response = AutoResponseManager()


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting IDS Engine API (ML-first)...")
    engine.load_models()
    logger.info("Models loaded, API ready")
    yield
    logger.info("Shutting down IDS Engine API")


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="NIDS IDS Engine API",
    description="Network Intrusion Detection System — ML-first real-time inference",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# WEBSOCKET BROADCAST
# ============================================================

async def broadcast(message: dict):
    """Send a message to all connected WebSocket clients."""
    dead = set()
    data = json.dumps(message)
    for ws in ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        models_loaded=engine._loaded,
        device=str(engine.device),
        uptime_seconds=time.time() - start_time,
        active_sessions=flow_buffer.session_count,
    )


@app.get("/metrics", response_model=MetricsResponse)
async def metrics():
    avg_lat = (total_latency_ms / total_predictions) if total_predictions else 0.0
    avg_conf = (total_confidence / total_predictions) if total_predictions else 0.0
    return MetricsResponse(
        total_predictions=total_predictions,
        class_counts=dict(prediction_counts),
        avg_latency_ms=avg_lat,
        avg_confidence=avg_conf,
        alerts_triggered=alert_count,
        uptime_seconds=time.time() - start_time,
    )


@app.post("/flows")
async def ingest_flows(req: FlowIngestRequest):
    """Accept YAF IPFIX flow dicts, run ML inference, return predictions."""
    global total_predictions, total_latency_ms, total_confidence, alert_count

    results = []
    t0 = time.time()

    # Phase A: Parse flows into feature vectors and buffer into windows
    ready_windows = []
    window_metadata = []  # Per-WINDOW metadata (tracks the session each window belongs to)
    last_flow_meta = None
    for flow in req.flows:
        # Parse raw YAF features (no mapping, no zero-filling)
        features = parse_yaf_flow(flow)
        src_port, dst_port = extract_ports(flow)

        src_ip = str(flow.get("sourceIPv4Address", flow.get("IPV4_SRC_ADDR", flow.get("src_ip", "0.0.0.0"))))
        dst_ip = str(flow.get("destinationIPv4Address", flow.get("IPV4_DST_ADDR", flow.get("dst_ip", "0.0.0.0"))))

        last_flow_meta = {
            'src_ip': src_ip, 'dst_ip': dst_ip,
            'src_port': src_port, 'dst_port': dst_port,
        }

        windows = flow_buffer.add_flow(features, src_ip, dst_ip, src_port, dst_port)
        # Each emitted window belongs to THIS flow's session (src_ip, dst_ip, dst_port)
        for w in windows:
            ready_windows.append(w)
            window_metadata.append({
                'src_ip': src_ip, 'dst_ip': dst_ip,
                'src_port': src_port, 'dst_port': dst_port,
            })

    # If no full windows yet, try partial window for early prediction
    if not ready_windows and last_flow_meta:
        fm = last_flow_meta
        partial = flow_buffer.get_partial_window(fm['src_ip'], fm['dst_ip'], fm['src_port'], fm['dst_port'])
        if partial is not None:
            ready_windows.append(partial)
            window_metadata.append(fm)

    # Phase B: Run ML inference
    ml_result = None
    if ready_windows:
        windows_arr = np.array(ready_windows, dtype=np.float32)
        ml_result = engine.predict(windows_arr, dataset_type=req.dataset_type)

    latency_ms = (time.time() - t0) * 1000.0
    now = datetime.now()

    # Buffer windows for adaptation (with IP-based labeling)
    for idx_w, w in enumerate(ready_windows):
        wm = window_metadata[idx_w]
        labeler.buffer_labeled_window(
            np.array(w, dtype=np.float32), now,
            src_ip=wm['src_ip'], dst_ip=wm['dst_ip'],
        )

    # Phase C: Build results — only include actual ML predictions from ready windows
    if ml_result:
        for i in range(len(ready_windows)):
            final_cls = ml_result['class_names'][i]
            final_conf = float(ml_result['confidence'][i])
            ml_probs = ml_result['probabilities'][i].tolist()
            sev = SEVERITY_MAP.get(final_cls, 'info')

            results.append(FlowIngestResult(
                predicted_class=final_cls,
                confidence=final_conf,
                severity=sev,
            ))

            prediction_counts[final_cls] += 1
            total_predictions += 1
            total_confidence += final_conf
            wm = window_metadata[i]
            labeler.record_prediction(now, final_cls,
                                      src_ip=wm['src_ip'], dst_ip=wm['dst_ip'])

            # Record for evaluation tracker
            eval_tracker.record(
                timestamp=t0, src_ip=wm['src_ip'], dst_ip=wm['dst_ip'],
                dst_port=wm['dst_port'], predicted=final_cls,
                rule='ml', confidence=final_conf,
            )

            # Broadcast to WebSocket clients
            if ws_clients:
                event = LivePredictionEvent(
                    type='prediction',
                    data={
                        'predicted_class': final_cls,
                        'confidence': final_conf,
                        'probabilities': ml_probs,
                        'severity': sev,
                        'latency_ms': latency_ms,
                        'timestamp': now.isoformat(),
                    },
                )
                asyncio.create_task(broadcast(event.model_dump()))

            # Alert on attack detection
            if final_cls != 'Benign':
                alert_count += 1

                # Auto-response: block attacker IP if thresholds met
                src_ip = wm.get('src_ip', '0.0.0.0')
                block_record = auto_response.record_alert(src_ip, final_cls, final_conf)
                if block_record:
                    logger.warning(f"AUTO-RESPONSE: Blocked {src_ip} — {final_cls} ({final_conf:.1%})")
                    if ws_clients:
                        block_event = {
                            'type': 'auto_block',
                            'ip': block_record.ip,
                            'attack_class': block_record.attack_class,
                            'confidence': block_record.confidence,
                            'blocked_at': block_record.blocked_at,
                            'reason': block_record.reason,
                        }
                        asyncio.create_task(broadcast(block_event))

                if ws_clients:
                    alert = AlertEvent(
                        type='alert',
                        severity=sev,
                        predicted_class=final_cls,
                        confidence=final_conf,
                        timestamp=now.isoformat(),
                        message=f"{final_cls} detected with {final_conf:.1%} confidence",
                    )
                    asyncio.create_task(broadcast(alert.model_dump()))

    total_latency_ms += latency_ms
    return {
        "results": [r.model_dump() for r in results],
        "flows_ingested": len(req.flows),
        "windows_predicted": len(ready_windows),
    }


@app.get("/attack/schedule")
async def get_schedule():
    return labeler.get_schedule()


@app.post("/attack/schedule")
async def register_attack_schedule(req: AttackScheduleRequest):
    """Register external ground truth (called by Attack Simulator UI)."""
    if req.attack_class not in UNIFIED_CLASSES:
        raise HTTPException(400, f"Unknown class: {req.attack_class}. Must be one of {UNIFIED_CLASSES}")

    start_dt = datetime.fromisoformat(req.start)
    end_dt = datetime.fromisoformat(req.end)
    duration_sec = (end_dt - start_dt).total_seconds()

    labeler.add_schedule_entry(
        attack_class=req.attack_class,
        attacker='A',
        start=start_dt,
        end=end_dt,
        attacker_ip=req.attacker_ip,
    )

    GROUND_TRUTH_BUFFER_SEC = 60
    eval_tracker.add_attack_window(
        label=req.attack_class,
        start=start_dt.timestamp(),
        end=end_dt.timestamp() + GROUND_TRUTH_BUFFER_SEC,
    )

    if ws_clients:
        event = {
            'event_type': 'attack_start',
            'attack_type': req.attack_class.lower(),
            'attack_class': req.attack_class,
            'started_at': req.start,
            'expected_end': req.end,
            'duration_seconds': int(duration_sec),
            'source': 'attack_simulator',
        }
        asyncio.create_task(broadcast(event))

    return {"status": "registered", "attack_class": req.attack_class, "duration": int(duration_sec)}


@app.get("/evaluation/detection-report")
async def get_detection_report():
    """SOC-style detection report: per-attack-window metrics + false alarm rate."""
    return eval_tracker.compute_detection_report()


@app.post("/evaluation/reset")
async def reset_evaluation():
    """Clear all evaluation data (attack windows + predictions)."""
    eval_tracker.reset()
    return {"status": "ok", "message": "Evaluation data cleared"}


# ============================================================
# ADAPTATION ENDPOINTS (read-only / maintenance)
# ============================================================

@app.get("/adaptation/buffer-stats")
async def adaptation_buffer_stats():
    """Get statistics about the adaptation buffer (accumulated labeled windows)."""
    return labeler.get_adaptation_stats()


@app.post("/adaptation/clear-buffer")
async def clear_adaptation_buffer():
    """Clear the adaptation buffer after successful retraining."""
    labeler.clear_adaptation_buffer()
    return {"status": "ok", "message": "Adaptation buffer cleared"}


@app.get("/adaptation/export-buffer")
async def export_buffer(offset: int = 0, limit: int = 500):
    """
    Export labeled windows from the adaptation buffer in chunks.
    Returns windows and labels as lists for download.
    Use offset/limit for pagination to avoid huge responses.
    """
    data = labeler.get_adaptation_data()
    if data['n_samples'] == 0:
        return {"n_samples": 0, "windows": [], "labels": [], "class_distribution": {}}

    end = min(offset + limit, data['n_samples'])
    windows_chunk = data['windows'][offset:end]
    labels_chunk = data['labels'][offset:end]

    return {
        "n_samples": data['n_samples'],
        "offset": offset,
        "limit": limit,
        "chunk_size": len(labels_chunk),
        "windows": windows_chunk.tolist(),
        "labels": labels_chunk.tolist(),
        "class_distribution": data['class_distribution'],
    }



# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    logger.info("WebSocket client connected, total=%d", len(ws_clients))
    try:
        while True:
            data = await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.discard(ws)
        logger.info("WebSocket client disconnected, total=%d", len(ws_clients))


# ============================================================
# AUTO-RESPONSE ENDPOINTS
# ============================================================

@app.get("/response/blocked")
async def get_blocked():
    """List all currently blocked IPs."""
    return {
        "enabled": auto_response.enabled,
        "blocked_ips": auto_response.get_blocked(),
        "count": len(auto_response.get_blocked()),
    }


@app.post("/response/block")
async def manual_block(ip: str, reason: str = "Manual block"):
    """Manually block an IP address."""
    record = auto_response.block_ip(ip, attack_class="Manual", confidence=1.0)
    if record is None:
        raise HTTPException(400, f"Could not block {ip} (already blocked or limit reached)")

    if ws_clients:
        event = {
            'type': 'auto_block',
            'ip': record.ip,
            'attack_class': record.attack_class,
            'confidence': record.confidence,
            'blocked_at': record.blocked_at,
            'reason': reason,
        }
        asyncio.create_task(broadcast(event))

    return {"status": "blocked", "ip": ip, "rule_number": record.rule_number}


@app.post("/response/unblock")
async def unblock(ip: str):
    """Unblock a specific IP address."""
    ok = auto_response.unblock_ip(ip)
    if not ok:
        raise HTTPException(404, f"IP {ip} is not currently blocked")

    if ws_clients:
        asyncio.create_task(broadcast({"type": "unblock", "ip": ip}))

    return {"status": "unblocked", "ip": ip}


@app.post("/response/unblock-all")
async def unblock_all():
    """Unblock all blocked IPs (demo reset)."""
    count = auto_response.unblock_all()
    if ws_clients:
        asyncio.create_task(broadcast({"type": "unblock_all", "count": count}))
    return {"status": "ok", "unblocked_count": count}
