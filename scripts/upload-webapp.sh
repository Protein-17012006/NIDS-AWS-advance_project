#!/usr/bin/env bash
# Upload ML webapp artifacts to S3 for WebServer deployment.
# The WebServer UserData pulls from s3://<BUCKET>/webapp/
# Usage: ./scripts/upload-webapp.sh [REGION]
set -euo pipefail

REGION="${1:-ap-southeast-1}"
WEBAPP_DIR="victim_webapp"

# Get S3 bucket name from CloudFormation
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name NIDS-Storage \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`DataBucketName`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -z "$BUCKET" ]; then
  echo "ERROR: Could not find NIDS-Storage stack. Deploy 04-storage.yaml first."
  exit 1
fi

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

echo "=== Uploading ML webapp to s3://${BUCKET}/webapp/ ==="

# Upload docker-compose.yml (rewritten for ECR images)
cat > /tmp/webapp-compose.yml << DCEOF
services:
  ml-backend:
    image: ${ECR_BASE}/nids-ml-backend:latest
    container_name: ml-backend
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./models:/app/models:ro
    environment:
      - PYTHONUNBUFFERED=1
    mem_limit: 512m
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')"]
      interval: 30s
      timeout: 5s
      retries: 3

  ml-frontend:
    image: ${ECR_BASE}/nids-ml-frontend:latest
    container_name: ml-frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      ml-backend:
        condition: service_healthy
    mem_limit: 128m
DCEOF

aws s3 cp /tmp/webapp-compose.yml "s3://${BUCKET}/webapp/docker-compose.yml" --region "$REGION"
rm /tmp/webapp-compose.yml
echo "  → docker-compose.yml"

# Upload trained model files
echo "=== Uploading model artifacts ==="
MODEL_COUNT=0
for f in "${WEBAPP_DIR}/models/"*; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  aws s3 cp "$f" "s3://${BUCKET}/webapp/models/${fname}" --region "$REGION" --quiet
  MODEL_COUNT=$((MODEL_COUNT + 1))
done
echo "  → ${MODEL_COUNT} model files uploaded"

# Upload ECR login helper script for WebServer
cat > /tmp/webapp-start.sh << 'STARTEOF'
#!/bin/bash
set -ex
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

# Login to ECR
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_BASE"

# Pull latest images
docker compose pull
docker compose up -d
STARTEOF
aws s3 cp /tmp/webapp-start.sh "s3://${BUCKET}/webapp/start.sh" --region "$REGION"
rm /tmp/webapp-start.sh
echo "  → start.sh"

echo ""
echo "=== Upload complete ==="
echo "Bucket: s3://${BUCKET}/webapp/"
aws s3 ls "s3://${BUCKET}/webapp/" --region "$REGION"
echo ""
echo "To deploy on WebServer, run via SSM:"
echo "  aws ssm send-command --instance-ids <WEBSERVER_ID> --document-name AWS-RunShellScript \\"
echo "    --parameters 'commands=[\"cd /opt/nids-webapp && bash start.sh\"]'"
