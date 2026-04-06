FROM python:3.10-slim

# Force IPv4 for apt (AWS VPC may not have IPv6 connectivity)
RUN echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        hping3 nmap hydra netcat-openbsd iputils-ping curl \
        iproute2 procps sshpass openssh-client && \
    pip install --no-cache-dir requests && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY attacks/ /opt/attacks/
COPY *.sh /app/
RUN chmod +x /app/*.sh /opt/attacks/*.sh 2>/dev/null || true

# Default: sleep forever — attacks are triggered via SSM RunCommand or docker compose
CMD ["sleep", "infinity"]
