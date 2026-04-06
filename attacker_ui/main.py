"""
Attack Simulator Web UI — FastAPI backend.

Runs on Attacker EC2 (port 9000). Provides a dark-themed web UI to
launch attack containers and register ground truth with the IDS Engine.
"""

import asyncio
import os
import subprocess
from datetime import datetime, timedelta

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

app = FastAPI(title="Attack Simulator")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# --- Configuration ---
IDS_API_URL = os.environ.get("IDS_API_URL", "http://engine.nids.local:8000")
TARGET_IP = os.environ.get("TARGET_IP")
ATTACKER_IP = os.environ.get("ATTACKER_IP")
COMPOSE_DIR = os.environ.get("COMPOSE_DIR", "/opt/nids-attacker")

# Active attack processes
_active: dict[str, subprocess.Popen] = {}

# WebSocket clients for live output
_ws_clients: set[WebSocket] = set()

# Attack definitions (must match docker-compose service names)
ATTACKS = {
    "ddos": {"label": "DDoS", "service": "ddos", "scale": 5, "default_dur": 60},
    "dos_slow": {"label": "DoS", "service": "dos", "scale": 1, "default_dur": 60},
    "bruteforce": {"label": "BruteForce", "service": "bruteforce", "scale": 1, "default_dur": 60},
    "infiltration": {"label": "Infiltration", "service": "infiltration", "scale": 1, "default_dur": 120},
}


async def _broadcast(msg: str):
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


async def _stream_output(proc: subprocess.Popen, attack_type: str):
    """Read process stdout line-by-line and broadcast via WebSocket."""
    loop = asyncio.get_event_loop()
    try:
        while True:
            line = await loop.run_in_executor(None, proc.stdout.readline)
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            await _broadcast(f"[{attack_type}] {text}")
    except Exception:
        pass
    finally:
        proc.wait()
        _active.pop(attack_type, None)
        await _broadcast(f"[{attack_type}] === FINISHED (exit {proc.returncode}) ===")


async def _register_ground_truth(attack_type: str, duration: int):
    """Register the attack schedule with the IDS Engine API for labeling."""
    cfg = ATTACKS[attack_type]
    now = datetime.utcnow()
    payload = {
        "attack_class": cfg["label"],
        "attacker_ip": ATTACKER_IP,
        "start": now.isoformat(),
        "end": (now + timedelta(seconds=duration)).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{IDS_API_URL}/attack/schedule", json=payload)
            if resp.status_code == 200:
                await _broadcast(f"[system] Ground truth registered for {cfg['label']} ({duration}s)")
            else:
                await _broadcast(f"[system] WARNING: failed to register ground truth: {resp.text}")
    except Exception as e:
        await _broadcast(f"[system] WARNING: could not reach IDS API: {e}")


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/launch/{attack_type}")
async def launch_attack(attack_type: str, duration: int = 60):
    if attack_type not in ATTACKS:
        return {"error": f"Unknown attack: {attack_type}"}
    if attack_type in _active:
        return {"error": f"{attack_type} already running"}

    cfg = ATTACKS[attack_type]
    service = cfg["service"]
    scale = cfg["scale"]

    env = {
        **os.environ,
        "TARGET_IP": TARGET_IP,
        "DURATION": str(duration),
        "ATTACKER_IP": ATTACKER_IP,
    }

    # Stop any leftover containers for this service
    subprocess.run(
        ["docker", "compose", "stop", service],
        cwd=COMPOSE_DIR, capture_output=True, env=env,
    )
    subprocess.run(
        ["docker", "compose", "rm", "-f", service],
        cwd=COMPOSE_DIR, capture_output=True, env=env,
    )

    # Launch attack container(s)
    cmd = ["docker", "compose", "up", "--scale", f"{service}={scale}", service]
    proc = subprocess.Popen(
        cmd, cwd=COMPOSE_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    _active[attack_type] = proc

    # Register ground truth with IDS Engine
    asyncio.create_task(_register_ground_truth(attack_type, duration))

    # Stream output via WebSocket
    asyncio.create_task(_stream_output(proc, attack_type))

    return {"status": "launched", "attack_type": attack_type, "duration": duration}


@app.post("/api/stop/{attack_type}")
async def stop_attack(attack_type: str):
    if attack_type not in ATTACKS:
        return {"error": f"Unknown attack: {attack_type}"}

    cfg = ATTACKS[attack_type]
    service = cfg["service"]

    # Kill the tracked process
    proc = _active.pop(attack_type, None)
    if proc:
        proc.terminate()

    # Also stop the docker container
    subprocess.run(
        ["docker", "compose", "stop", service],
        cwd=COMPOSE_DIR, capture_output=True,
    )
    await _broadcast(f"[{attack_type}] Stopped by user")
    return {"status": "stopped", "attack_type": attack_type}


@app.get("/api/status")
async def status():
    return {
        "active": list(_active.keys()),
        "attacks": {k: v["label"] for k, v in ATTACKS.items()},
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(ws)
