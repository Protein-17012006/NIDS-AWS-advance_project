Build a complete Network Intrusion Detection System (NIDS) on the AWS Cloud platform, using a Deep Learning ensemble model that combines multiple architectures (CNN+LSTM, BiLSTM, Transformer) with a Meta-Learner, capable of:

- Detecting 4 types of attacks: **DDoS**, **DoS**, **BruteForce**, **Infiltration**
- Classifying real-time traffic from live network traffic
- Automatically responding by blocking attacking IPs via Network ACL
- Automatically collecting data periodically to retrain the model
- Visual real-time monitoring dashboard
<img width="2011" height="2001" alt="aws_NIDS drawio" src="https://github.com/user-attachments/assets/e8492b09-596f-4b8c-b0dd-80628f1f4639" />
1. **Complete AWS Infrastructure**: 10 CloudFormation stacks, multi-subnet VPC, EC2, ECS Fargate, S3, ECR, ALB, NLB, NAT Gateway, Traffic Mirror, CloudWatch, SNS, Lambda, EventBridge

2. **ML Pipeline End-to-End**: From raw network packets → YAF flow analysis → feature extraction → 3 deep learning models → meta-learner ensemble → 5-class prediction → auto-response

3. **4 Simulated Attack Types**: DDoS (HTTP flood), DoS (Slowloris), BruteForce (SSH/HTTP), Infiltration (multi-phase APT) — with realistic multi-phase scripts

4. **9 User Personas**: Simulates diverse real traffic (Office Workers, Developers, Managers, IoT sensors) with different behavior patterns

5. **Monitoring Dashboard**: React 5. TypeScript real-time via WebSocket, attack control panel, detection reports, blocked IP management

6. **Auto-Response**: Automatically blocks attack IPs via NACL rules when confidence >85% and ≥3 alerts

7. **Data Collection Pipeline**: Lambda automatically collects labeled data every hour → S3 → ready for retraining

8. **ML WebApp**: 5 sklearn models × 3 datasets for interactive exploration
