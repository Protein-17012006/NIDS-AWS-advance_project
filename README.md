Build a complete Network Intrusion Detection System (NIDS) on the AWS Cloud platform, using a Deep Learning ensemble model that combines multiple architectures (CNN+LSTM, BiLSTM, Transformer) with a Meta-Learner, capable of:

- Detecting 4 types of attacks: **DDoS**, **DoS**, **BruteForce**, **Infiltration**
- Classifying real-time traffic from live network traffic
- Automatically responding by blocking attacking IPs via Network ACL
- Automatically collecting data periodically to retrain the model
- Visual real-time monitoring dashboard
<img width="2011" height="2001" alt="aws_NIDS drawio" src="https://github.com/user-attachments/assets/e8492b09-596f-4b8c-b0dd-80628f1f4639" />
| Components | Technology | Roles |

|-----------|-----------|---------|

| VPC Network | AWS VPC, 4 Subnets, NAT Gateway | Isolated Network Infrastructure |

| IDS Engine | FastAPI + PyTorch on ECS Fargate | Core ML Inference Engine |

| Sensor | YAF + Supermediator on EC2 | Traffic Capture and Analysis |

| Traffic Mirror | AWS VPC Traffic Mirroring | Network Traffic Replication |

| Dashboard | React + TypeScript on ECS Fargate | Monitoring Interface |

| Attacker | Docker Containers on EC2 | Attack Simulation |

| User Simulator | 9 Docker Containers on EC2 | Real User Simulation |

| Data Collection | AWS Lambda + EventBridge | Automated Data Collection |

| Monitoring | CloudWatch + SNS | Alerts and Monitoring |

| ML WebApp | FastAPI + React on EC2 | Predictive ML Webapp |
