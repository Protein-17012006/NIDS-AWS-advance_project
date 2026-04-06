#!/usr/bin/env bash
# Build and push Docker images to ECR.
# Usage: ./scripts/build-push-images.sh [AWS_ACCOUNT_ID] [REGION]
set -euo pipefail

ACCOUNT="${1:?Usage: $0 <AWS_ACCOUNT_ID> [REGION]}"
REGION="${2:-ap-southeast-1}"
ECR_BASE="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

echo "=== Logging in to ECR ==="
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_BASE"

# Create repos if they don't exist
for repo in nids-ids-engine nids-dashboard nids-ml-backend nids-ml-frontend; do
  aws ecr describe-repositories --repository-names "$repo" --region "$REGION" 2>/dev/null || \
    aws ecr create-repository --repository-name "$repo" --region "$REGION"
done

TAG="$(date +%Y%m%d-%H%M%S)"

echo "=== Building IDS Engine (tag: $TAG) ==="
docker build -t "nids-ids-engine:${TAG}" -f ids_engine/Dockerfile .
docker tag "nids-ids-engine:${TAG}" "${ECR_BASE}/nids-ids-engine:${TAG}"
docker tag "nids-ids-engine:${TAG}" "${ECR_BASE}/nids-ids-engine:latest"
docker push "${ECR_BASE}/nids-ids-engine:${TAG}"
docker push "${ECR_BASE}/nids-ids-engine:latest"

echo "=== Building Dashboard (tag: $TAG) ==="
docker build -t "nids-dashboard:${TAG}" -f dashboard/Dockerfile ./dashboard
docker tag "nids-dashboard:${TAG}" "${ECR_BASE}/nids-dashboard:${TAG}"
docker tag "nids-dashboard:${TAG}" "${ECR_BASE}/nids-dashboard:latest"
docker push "${ECR_BASE}/nids-dashboard:${TAG}"
docker push "${ECR_BASE}/nids-dashboard:latest"

echo "=== Building ML Backend (tag: $TAG) ==="
docker build -t "nids-ml-backend:${TAG}" -f victim_webapp/Dockerfile.backend ./victim_webapp
docker tag "nids-ml-backend:${TAG}" "${ECR_BASE}/nids-ml-backend:${TAG}"
docker tag "nids-ml-backend:${TAG}" "${ECR_BASE}/nids-ml-backend:latest"
docker push "${ECR_BASE}/nids-ml-backend:${TAG}"
docker push "${ECR_BASE}/nids-ml-backend:latest"

echo "=== Building ML Frontend (tag: $TAG) ==="
docker build -t "nids-ml-frontend:${TAG}" -f victim_webapp/Dockerfile.frontend ./victim_webapp
docker tag "nids-ml-frontend:${TAG}" "${ECR_BASE}/nids-ml-frontend:${TAG}"
docker tag "nids-ml-frontend:${TAG}" "${ECR_BASE}/nids-ml-frontend:latest"
docker push "${ECR_BASE}/nids-ml-frontend:${TAG}"
docker push "${ECR_BASE}/nids-ml-frontend:latest"

echo ""
echo "=== Images pushed ==="
echo "IDS Engine:  ${ECR_BASE}/nids-ids-engine:${TAG}"
echo "Dashboard:   ${ECR_BASE}/nids-dashboard:${TAG}"
echo "ML Backend:  ${ECR_BASE}/nids-ml-backend:${TAG}"
echo "ML Frontend: ${ECR_BASE}/nids-ml-frontend:${TAG}"
echo ""
echo "Use these URIs as parameters for cfn/07-ecs.yaml:"
echo "  IDSEngineImage=${ECR_BASE}/nids-ids-engine:${TAG}"
echo "  DashboardImage=${ECR_BASE}/nids-dashboard:${TAG}"
