#!/usr/bin/env bash
# Upload model weights to S3 for ECS tasks to download at startup.
# Usage: ./scripts/upload-models.sh [REGION]
set -euo pipefail

REGION="${1:-ap-southeast-1}"
MODEL_DIR="Project/Model/Model_IRM"

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

echo "Uploading models from ${MODEL_DIR}/ to s3://${BUCKET}/models/"

for f in "$MODEL_DIR"/*.pth "$MODEL_DIR"/*.pkl "$MODEL_DIR"/*.npz; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  echo "  → $fname"
  aws s3 cp "$f" "s3://${BUCKET}/models/${fname}" --region "$REGION"
done

echo ""
echo "=== Upload complete ==="
echo "Bucket: s3://${BUCKET}/models/"
aws s3 ls "s3://${BUCKET}/models/" --region "$REGION"
