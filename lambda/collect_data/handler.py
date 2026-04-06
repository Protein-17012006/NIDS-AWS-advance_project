"""
Lambda: Collect labeled data from IDS Engine adaptation buffer -> S3.

Triggered by EventBridge every hour. Paginates through the buffer,
streams gzip JSON to /tmp (compatible with retrain_local.py), uploads
to S3, then clears the buffer.

Single-pass: streams windows to disk, accumulates labels in memory (tiny).
"""

import gzip
import json
import os
import time
import uuid
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

import boto3

# ── Config ──────────────────────────────────────────────────
IDS_ENGINE_URL = os.environ.get("IDS_ENGINE_URL", "http://engine.nids.local:8000")
S3_BUCKET = os.environ["S3_BUCKET"]
S3_PREFIX = os.environ.get("S3_PREFIX", "collected-data")
PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "1000"))
TMP_FILE = "/tmp/collected.json.gz"
MAX_RETRIES = 3

s3 = boto3.client("s3")
cw = boto3.client("cloudwatch")


def _get(path: str) -> dict:
    """HTTP GET with retries."""
    url = f"{IDS_ENGINE_URL}{path}"
    for attempt in range(MAX_RETRIES):
        try:
            req = Request(url, method="GET")
            req.add_header("Accept", "application/json")
            with urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except (URLError, OSError, TimeoutError) as e:
            print(f"  [WARN] GET {path} attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)


def _post(path: str) -> dict:
    """HTTP POST helper."""
    url = f"{IDS_ENGINE_URL}{path}"
    req = Request(url, method="POST", data=b"")
    req.add_header("Accept", "application/json")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _put_metric(name: str, value: float, unit: str = "Count"):
    cw.put_metric_data(
        Namespace="NIDS/DataCollection",
        MetricData=[{
            "MetricName": name,
            "Value": value,
            "Unit": unit,
        }],
    )


def handler(event, context):
    print("=== Data Collection Lambda START ===")

    # 1. Check buffer stats
    stats = _get("/adaptation/buffer-stats")
    n_samples = stats.get("n_samples", 0)
    print(f"Buffer stats: {json.dumps(stats)}")

    if n_samples == 0:
        print("Buffer empty - nothing to collect.")
        _put_metric("WindowsCollected", 0)
        return {"status": "empty", "n_samples": 0}

    # 2. Single-pass: stream windows to gzip, accumulate labels in memory
    now = datetime.now(timezone.utc)
    total = 0
    offset = 0
    all_labels = []  # ints only, ~50KB for 50K samples

    with gzip.open(TMP_FILE, "wt", encoding="utf-8") as gz:
        gz.write('{"windows": [')
        first_window = True

        while offset < n_samples:
            page = _get(f"/adaptation/export-buffer?offset={offset}&limit={PAGE_SIZE}")
            chunk_size = page.get("chunk_size", 0)
            if chunk_size == 0:
                print(f"  [WARN] chunk_size=0 at offset={offset}, expected more data (n_samples={n_samples})")
                break

            # Stream windows to disk
            for w in page["windows"]:
                if not first_window:
                    gz.write(",")
                json.dump(w, gz)
                first_window = False

            # Accumulate labels in memory (cheap — just ints)
            all_labels.extend(page["labels"])

            total += chunk_size
            offset += chunk_size
            print(f"  Fetched offset={offset - chunk_size}, size={chunk_size}, total={total}")
            del page

        # Write labels + metadata
        gz.write('], "labels": ')
        json.dump(all_labels, gz)
        gz.write(f', "collected_at": "{now.isoformat()}"')
        gz.write(f', "n_samples": {total}')
        gz.write(f', "class_distribution": {json.dumps(stats.get("class_distribution", {}))}')
        gz.write("}")

    file_size = os.path.getsize(TMP_FILE)
    print(f"Written {TMP_FILE}: {file_size} bytes, {total} samples")

    if total == 0:
        print("No windows collected - skipping upload.")
        return {"status": "empty", "n_samples": 0}

    # 3. Upload to S3
    date_prefix = now.strftime("%Y-%m-%d")
    hour_prefix = now.strftime("%H00")
    file_id = uuid.uuid4().hex[:8]
    s3_key = f"{S3_PREFIX}/{date_prefix}/{hour_prefix}-{file_id}.json.gz"

    s3.upload_file(TMP_FILE, S3_BUCKET, s3_key, ExtraArgs={"ContentType": "application/gzip"})
    print(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")

    # 4. Clear buffer after successful upload
    clear_resp = _post("/adaptation/clear-buffer")
    print(f"Buffer cleared: {json.dumps(clear_resp)}")

    # 5. Publish CloudWatch metric
    _put_metric("WindowsCollected", total)

    os.remove(TMP_FILE)

    result = {
        "status": "ok",
        "n_samples": total,
        "s3_key": s3_key,
        "compressed_bytes": file_size,
        "class_distribution": stats.get("class_distribution", {}),
    }
    print(f"=== Data Collection Lambda DONE === {json.dumps(result)}")
    return result
