"""
User Simulator — Each container represents one virtual user with a
distinct persona (traffic pattern, timing, protocol mix).

The persona is selected via the USER_PROFILE env var (0-8).
Traffic targets the WebServer (10.0.1.10) running:
  - ML WebApp frontend on port 3000 (React SPA + API proxy)
  - Apache httpd on port 80
  - DVWA on port 8080
  - Weak SSH on port 2222
All containers run on the UserSimulator EC2 with unique VPC IPs (ipvlan L2)
so the NIDS sensor sees distinct session keys per user.
"""

import logging
import os
import random
import socket
import struct
import time

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
log = logging.getLogger("user-sim")

# ── Targets ─────────────────────────────────────────────────
WEB_SERVER = os.environ.get("WEB_SERVER_IP")
DNS_SERVER = os.environ.get("DNS_SERVER_IP", "10.0.1.12")
WEBAPP_PORT = int(os.environ.get("WEBAPP_PORT", "80"))

# ── Persona config ──────────────────────────────────────────
PROFILE_ID = int(os.environ.get("USER_PROFILE", "0"))

# ML WebApp resources
DATASETS = ["cic2017", "cic2018", "nf_uq"]
MODELS = ["knn", "logistic_regression", "svm", "decision_tree", "random_forest"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) Mobile/15E148",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Edge/120.0",
    "python-requests/2.31.0",
]

DNS_NAMES = [
    "web.nids.local", "ml-webapp.nids.local",
    "www.example.com", "google.com", "github.com",
    "api.company.local", "sklearn.org",
]


# ═══════════════════════════════════════════════════════════
# Traffic action primitives — ML WebApp
# ═══════════════════════════════════════════════════════════

def webapp_get(path="/", port=WEBAPP_PORT, timeout=10):
    """HTTP GET to ML WebApp."""
    try:
        resp = requests.get(
            f"http://{WEB_SERVER}:{port}{path}",
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=timeout,
        )
        _ = resp.content
    except requests.RequestException:
        pass


def webapp_post_json(path, payload, port=WEBAPP_PORT, timeout=30):
    """HTTP POST JSON to ML WebApp API."""
    try:
        resp = requests.post(
            f"http://{WEB_SERVER}:{port}{path}",
            json=payload,
            headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        _ = resp.content
    except requests.RequestException:
        pass


def webapp_put_json(path, payload, port=WEBAPP_PORT, timeout=10):
    """HTTP PUT JSON to ML WebApp API."""
    try:
        resp = requests.put(
            f"http://{WEB_SERVER}:{port}{path}",
            json=payload,
            headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        _ = resp.content
    except requests.RequestException:
        pass


def webapp_delete(path, port=WEBAPP_PORT, timeout=10):
    """HTTP DELETE to ML WebApp API."""
    try:
        resp = requests.delete(
            f"http://{WEB_SERVER}:{port}{path}",
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=timeout,
        )
        _ = resp.content
    except requests.RequestException:
        pass


def load_spa():
    """Simulate loading the React SPA — index.html + JS bundle + initial API calls."""
    sess = requests.Session()
    sess.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    try:
        sess.get(f"http://{WEB_SERVER}:{WEBAPP_PORT}/", timeout=10)
        time.sleep(random.uniform(0.05, 0.2))
        sess.get(f"http://{WEB_SERVER}:{WEBAPP_PORT}/static/js/main.06445457.js", timeout=10)
        time.sleep(random.uniform(0.05, 0.2))
        # React app mounts → fetches initial data
        sess.get(f"http://{WEB_SERVER}:{WEBAPP_PORT}/api/health", timeout=10)
        sess.get(f"http://{WEB_SERVER}:{WEBAPP_PORT}/api/datasets", timeout=10)
        sess.get(f"http://{WEB_SERVER}:{WEBAPP_PORT}/api/models", timeout=10)
    except requests.RequestException:
        pass
    finally:
        sess.close()


def run_prediction():
    """POST /api/predict with a random dataset + model."""
    dataset = random.choice(DATASETS)
    model = random.choice(MODELS)
    webapp_post_json("/api/predict", {"dataset": dataset, "model": model})


def run_compare():
    """POST /api/compare — compare 2-5 models on a dataset."""
    dataset = random.choice(DATASETS)
    n = random.randint(2, 5)
    models = random.sample(MODELS, k=min(n, len(MODELS)))
    webapp_post_json("/api/compare", {"dataset": dataset, "models": models})


def browse_datasets():
    """GET /api/datasets."""
    webapp_get("/api/datasets")


def browse_models():
    """GET /api/models."""
    webapp_get("/api/models")


def check_health():
    """GET /api/health."""
    webapp_get("/api/health")


def update_settings():
    """PUT /api/settings with random test_size and seed."""
    payload = {
        "test_size": round(random.uniform(0.1, 0.4), 2),
        "random_seed": random.randint(0, 99999),
    }
    webapp_put_json("/api/settings", payload)


def get_settings():
    """GET /api/settings."""
    webapp_get("/api/settings")


def clear_cache():
    """DELETE /api/cache."""
    webapp_delete("/api/cache")


def browsing_session(pages=None, think_range=(1.0, 4.0)):
    """Multi-page browsing session on the ML WebApp.

    Simulates a user navigating: load SPA → datasets → models → predict.
    """
    actions = [
        lambda: webapp_get("/"),
        lambda: webapp_get("/api/health"),
        lambda: webapp_get("/api/datasets"),
        lambda: webapp_get("/api/models"),
        lambda: webapp_get("/api/settings"),
        lambda: run_prediction(),
    ]
    n = pages or random.randint(2, len(actions))
    selected = random.sample(actions, k=min(n, len(actions)))
    for action in selected:
        action()
        time.sleep(random.uniform(*think_range))


def rapid_api_burst(n_requests=None):
    """Rapid succession of API predict calls — simulates automated testing."""
    n = n_requests or random.randint(3, 6)
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Content-Type": "application/json",
    })
    try:
        for _ in range(n):
            dataset = random.choice(DATASETS)
            model = random.choice(MODELS)
            resp = sess.post(
                f"http://{WEB_SERVER}:{WEBAPP_PORT}/api/predict",
                json={"dataset": dataset, "model": model},
                timeout=30,
            )
            _ = resp.content
            time.sleep(random.uniform(0.1, 0.5))
    except requests.RequestException:
        pass
    finally:
        sess.close()


def webapp_login():
    """POST /api/login with valid credentials — normal user login flow."""
    try:
        resp = requests.post(
            f"http://{WEB_SERVER}:{WEBAPP_PORT}/api/login",
            json={"username": "admin", "password": "admin123"},
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=10,
        )
        _ = resp.content
    except requests.RequestException:
        pass


# ═══════════════════════════════════════════════════════════
# Traffic action primitives — Other services
# ═══════════════════════════════════════════════════════════

def httpd_browse():
    """Browse Apache httpd on port 80."""
    paths = ["/", "/index.html", "/icons/", "/manual/"]
    try:
        requests.get(
            f"http://{WEB_SERVER}:80{random.choice(paths)}",
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=5,
        )
    except requests.RequestException:
        pass


def dvwa_browse():
    """Browse DVWA on port 8080."""
    paths = ["/", "/login.php", "/setup.php", "/index.php"]
    try:
        requests.get(
            f"http://{WEB_SERVER}:8080{random.choice(paths)}",
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=5,
        )
    except requests.RequestException:
        pass


def dns_query(name=None):
    """Raw DNS A-record UDP query."""
    name = name or random.choice(DNS_NAMES)
    try:
        txn = random.randint(0, 65535)
        hdr = struct.pack(">HHHHHH", txn, 0x0100, 1, 0, 0, 0)
        qname = b""
        for label in name.split("."):
            qname += struct.pack("B", len(label)) + label.encode()
        qname += b"\x00"
        pkt = hdr + qname + struct.pack(">HH", 1, 1)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(pkt, (DNS_SERVER, 53))
        s.recvfrom(512)
        s.close()
    except (socket.error, OSError):
        pass


def ssh_banner(port=2222):
    """TCP connect + read SSH banner (benign admin check)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((WEB_SERVER, port))
        s.recv(1024)
        s.close()
    except (socket.error, OSError):
        pass


# ═══════════════════════════════════════════════════════════
# User Persona Definitions (profiles 0-8 deployed)
# ═══════════════════════════════════════════════════════════

PERSONAS = {
    # ── Data Analysts (0-2): Heavy ML WebApp usage ──────────
    0: {
        "name": "DataAnalyst-1",
        "actions": [
            (lambda: webapp_login(),                                       8),
            (lambda: load_spa(),                                          12),
            (lambda: browsing_session(random.randint(3, 6), (1.0, 4.0)), 20),
            (lambda: run_prediction(),                                    25),
            (lambda: run_compare(),                                       15),
            (lambda: browse_datasets(),                                   10),
            (lambda: browse_models(),                                      5),
            (lambda: dns_query(),                                          5),
        ],
        "base_interval": 3.0,
        "jitter": 0.4,
        "burst_prob": 0.15,
        "burst_multiplier": 3.0,
    },
    1: {
        "name": "DataAnalyst-2",
        "actions": [
            (lambda: webapp_login(),                                       8),
            (lambda: load_spa(),                                           8),
            (lambda: browsing_session(random.randint(2, 4), (2.0, 6.0)), 19),
            (lambda: run_prediction(),                                    20),
            (lambda: run_compare(),                                       18),
            (lambda: get_settings(),                                       9),
            (lambda: browse_datasets(),                                   10),
            (lambda: dns_query(),                                          8),
        ],
        "base_interval": 4.0,
        "jitter": 0.5,
        "burst_prob": 0.1,
        "burst_multiplier": 2.5,
    },
    2: {
        "name": "DataAnalyst-3",
        "actions": [
            (lambda: load_spa(),                                          10),
            (lambda: rapid_api_burst(random.randint(3, 5)),               20),
            (lambda: run_prediction(),                                    20),
            (lambda: run_compare(),                                       15),
            (lambda: update_settings(),                                   10),
            (lambda: clear_cache(),                                        5),
            (lambda: browse_models(),                                     10),
            (lambda: dns_query(),                                         10),
        ],
        "base_interval": 2.0,
        "jitter": 0.3,
        "burst_prob": 0.2,
        "burst_multiplier": 2.0,
    },

    # ── Developers (3-4): API-heavy + SSH + testing ─────────
    3: {
        "name": "Developer-1",
        "actions": [
            (lambda: webapp_login(),                                       8),
            (lambda: rapid_api_burst(random.randint(4, 8)),              22),
            (lambda: run_prediction(),                                    18),
            (lambda: ssh_banner(2222),                                    10),
            (lambda: check_health(),                                      14),
            (lambda: update_settings(),                                   10),
            (lambda: clear_cache(),                                        8),
            (lambda: dns_query(),                                         10),
        ],
        "base_interval": 1.5,
        "jitter": 0.6,
        "burst_prob": 0.3,
        "burst_multiplier": 4.0,
    },
    4: {
        "name": "Developer-2",
        "actions": [
            (lambda: webapp_login(),                                       8),
            (lambda: rapid_api_burst(random.randint(3, 6)),              18),
            (lambda: run_prediction(),                                    18),
            (lambda: run_compare(),                                       13),
            (lambda: ssh_banner(2222),                                    10),
            (lambda: check_health(),                                      10),
            (lambda: browse_datasets(),                                    8),
            (lambda: dns_query(),                                         15),
        ],
        "base_interval": 1.8,
        "jitter": 0.5,
        "burst_prob": 0.25,
        "burst_multiplier": 3.5,
    },

    # ── Managers (5-6): Light browsing, view results ────────
    5: {
        "name": "Manager-1",
        "actions": [
            (lambda: webapp_login(),                                      10),
            (lambda: load_spa(),                                          15),
            (lambda: browsing_session(random.randint(1, 2), (3.0, 8.0)), 28),
            (lambda: check_health(),                                      15),
            (lambda: browse_datasets(),                                   12),
            (lambda: dns_query(),                                         20),
        ],
        "base_interval": 8.0,
        "jitter": 0.4,
        "burst_prob": 0.05,
        "burst_multiplier": 2.0,
    },
    6: {
        "name": "Manager-2",
        "actions": [
            (lambda: load_spa(),                                          15),
            (lambda: check_health(),                                      20),
            (lambda: get_settings(),                                      15),
            (lambda: browse_models(),                                     20),
            (lambda: run_prediction(),                                    10),
            (lambda: dns_query(),                                         20),
        ],
        "base_interval": 10.0,
        "jitter": 0.3,
        "burst_prob": 0.05,
        "burst_multiplier": 1.5,
    },

    # ── Monitoring Agents (7-8): Periodic health + service checks
    7: {
        "name": "Monitor-HealthCheck",
        "actions": [
            (lambda: check_health(),                                      50),
            (lambda: webapp_get("/"),                                      20),
            (lambda: browse_datasets(),                                   15),
            (lambda: dns_query("ml-webapp.nids.local"),                   15),
        ],
        "base_interval": 5.0,
        "jitter": 0.1,
        "burst_prob": 0.0,
        "burst_multiplier": 1.0,
    },
    8: {
        "name": "Monitor-ServiceCheck",
        "actions": [
            (lambda: check_health(),                                      30),
            (lambda: httpd_browse(),                                      20),
            (lambda: dvwa_browse(),                                       15),
            (lambda: ssh_banner(2222),                                    15),
            (lambda: dns_query("web.nids.local"),                         20),
        ],
        "base_interval": 8.0,
        "jitter": 0.05,
        "burst_prob": 0.02,
        "burst_multiplier": 3.0,
    },
}


# ═══════════════════════════════════════════════════════════
# Main loop
# ═══════════════════════════════════════════════════════════

def pick_action(persona: dict):
    """Weighted random selection of an action from persona."""
    actions, weights = zip(*persona["actions"])
    return random.choices(actions, weights=weights, k=1)[0]


def get_interval(persona: dict) -> float:
    """Compute sleep interval with persona-specific jitter and bursts."""
    base = persona["base_interval"]
    jitter = persona["jitter"]
    interval = base * random.uniform(1.0 - jitter, 1.0 + jitter)

    if random.random() < persona["burst_prob"]:
        interval /= persona["burst_multiplier"]

    return max(interval, 0.1)


def main():
    persona = PERSONAS.get(PROFILE_ID)
    if persona is None:
        log.error("Unknown USER_PROFILE=%d, valid: 0-%d", PROFILE_ID, max(PERSONAS.keys()))
        return

    log.info("Starting persona %d: %s (interval=%.1fs, jitter=%.0f%%)",
             PROFILE_ID, persona["name"], persona["base_interval"],
             persona["jitter"] * 100)
    log.info("  Target WebServer=%s:%d, DNS=%s", WEB_SERVER, WEBAPP_PORT, DNS_SERVER)

    startup_delay = PROFILE_ID * random.uniform(0.5, 2.0)
    log.info("  Startup delay: %.1fs", startup_delay)
    time.sleep(startup_delay)

    counter = 0
    while True:
        try:
            action = pick_action(persona)
            action()
            counter += 1
            if counter % 50 == 0:
                log.info("[%s] %d actions completed", persona["name"], counter)
        except Exception as exc:
            log.debug("Action error: %s", exc)
        interval = get_interval(persona)
        time.sleep(interval)


if __name__ == "__main__":
    main()
