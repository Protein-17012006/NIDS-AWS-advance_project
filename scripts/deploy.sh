#!/usr/bin/env bash
# Deploy all CloudFormation stacks in order.
# Usage: ./scripts/deploy.sh <KEY_PAIR_NAME> <IDS_ENGINE_IMAGE> <DASHBOARD_IMAGE> [ALERT_EMAIL] [REGION]
set -euo pipefail

KEY_PAIR="${1:?Usage: $0 <KEY_PAIR_NAME> <IDS_ENGINE_IMAGE> <DASHBOARD_IMAGE> [ALERT_EMAIL] [REGION]}"
ENGINE_IMAGE="${2:?}"
DASHBOARD_IMAGE="${3:?}"
ALERT_EMAIL="${4:-}"
REGION="${5:-ap-southeast-1}"

# Get current admin IP for SG stack (reuse existing value)
ADMIN_IP=$(aws cloudformation describe-stacks --stack-name NIDS-SG --region "$REGION" \
  --query 'Stacks[0].Parameters[?ParameterKey==`AdminIP`].ParameterValue' --output text 2>/dev/null || echo "")

deploy_stack() {
  local name="$1"
  local template="$2"
  shift 2
  local params=("$@")

  echo ""
  echo "=== Deploying $name ==="
  local cmd=(
    aws cloudformation deploy
    --template-file "$template"
    --stack-name "$name"
    --region "$REGION"
    --capabilities CAPABILITY_NAMED_IAM
    --no-fail-on-empty-changeset
  )
  if [ "${#params[@]}" -gt 0 ]; then
    cmd+=(--parameter-overrides "${params[@]}")
  fi
  "${cmd[@]}"
  echo "  → $name deployed"
}

deploy_stack "NIDS-VPC"          cfn/01-vpc.yaml
deploy_stack "NIDS-SG"           cfn/02-security-groups.yaml  "AdminIP=${ADMIN_IP}"
deploy_stack "NIDS-IAM"          cfn/03-iam.yaml
deploy_stack "NIDS-Storage"      cfn/04-storage.yaml
deploy_stack "NIDS-Compute"      cfn/05-compute.yaml      "KeyPairName=${KEY_PAIR}"
deploy_stack "NIDS-TrafficMirror" cfn/06-traffic-mirror.yaml
deploy_stack "NIDS-ECS"          cfn/07-ecs.yaml          "IDSEngineImage=${ENGINE_IMAGE}" "DashboardImage=${DASHBOARD_IMAGE}"

if [ -n "$ALERT_EMAIL" ]; then
  deploy_stack "NIDS-Monitoring" cfn/08-monitoring.yaml    "AlertEmail=${ALERT_EMAIL}"
fi

# NOTE: Do NOT deploy 09-alb.yaml — it is a legacy template.
# The ALB is already included in 07-ecs.yaml.

# Deploy NLB for public access to ML webapp on WebServer
deploy_stack "NIDS-NLB-WebApp"   cfn/10-nlb-webapp.yaml

# Deploy Lambda data collection pipeline
deploy_stack "NIDS-DataCollection" cfn/11-data-collection.yaml

echo ""
echo "=== All stacks deployed ==="

# ── Post-deploy: configure .env on Attacker & UserSimulator ──
NLB_DNS=$(aws cloudformation describe-stacks --stack-name NIDS-NLB-WebApp --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`WebAppNLBDNS`].OutputValue' --output text 2>/dev/null || echo "")

if [ -n "$NLB_DNS" ]; then
  echo ""
  echo "=== Configuring EC2 instances via SSM ==="

  ATTACKER_ID=$(aws cloudformation describe-stacks --stack-name NIDS-Compute --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`AttackerId`].OutputValue' --output text)
  ATTACKER_IP=$(aws cloudformation describe-stacks --stack-name NIDS-Compute --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`AttackerIP`].OutputValue' --output text)

  # Write .env on Attacker EC2
  aws ssm send-command --region "$REGION" \
    --instance-ids "$ATTACKER_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=[
      'cat > /opt/nids-attacker/.env << EOF',
      'TARGET_IP=${NLB_DNS}',
      'ATTACKER_IP=${ATTACKER_IP}',
      'IDS_API_URL=http://engine.nids.local:8000',
      'EOF'
    ]" \
    --comment "Configure attacker .env with NLB DNS" \
    --output text --query 'Command.CommandId'
  echo "  → Attacker .env configured (TARGET_IP=$NLB_DNS)"

  # Detect UserSimulator instance ID (tagged NIDS-UserSimulator)
  USERSIM_ID=$(aws ec2 describe-instances --region "$REGION" \
    --filters "Name=tag:Name,Values=NIDS-UserSimulator" "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text)

  if [ "$USERSIM_ID" != "None" ] && [ -n "$USERSIM_ID" ]; then
    aws ssm send-command --region "$REGION" \
      --instance-ids "$USERSIM_ID" \
      --document-name "AWS-RunShellScript" \
      --parameters "commands=[
        'cat > /opt/nids-user-simulator/.env << EOF',
        'WEB_SERVER_IP=${NLB_DNS}',
        'EOF'
      ]" \
      --comment "Configure user-simulator .env with NLB DNS" \
      --output text --query 'Command.CommandId'
    echo "  → UserSimulator .env configured (WEB_SERVER_IP=$NLB_DNS)"
  fi
fi

echo ""
echo "Dashboard URL:  $(aws cloudformation describe-stacks --stack-name NIDS-ECS --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`ALBDnsName`].OutputValue' --output text)"
echo "ML WebApp URL:  $(aws cloudformation describe-stacks --stack-name NIDS-NLB-WebApp --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`WebAppURL`].OutputValue' --output text 2>/dev/null || echo 'N/A')"
