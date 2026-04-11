1. The project focuses on building a comprehensive Network Intrusion Detection System (NIDS) on the AWS cloud platform, capable of analyzing and classifying network traffic in real time. The system utilizes an Ensemble deep learning architecture, combining advanced models such as CNN+LSTM, BiLSTM, and Transformer, along with a Meta-Learner mechanism to accurately identify four common attack types: DDoS, DoS, BruteForce, and Infiltration. In addition to detection capabilities, the system integrates an auto-response mechanism and an automated data collection pipeline (CI/CD for ML data) to continuously refine the model.

- Detecting 4 types of attacks: **DDoS**, **DoS**, **BruteForce**, **Infiltration**
- Classifying real-time traffic from live network traffic
- Automatically responding by blocking attacking IPs via Network ACL
- Automatically collecting data periodically to retrain the model
- Visual real-time monitoring dashboard
<img width="803" height="795" alt="image" src="https://github.com/user-attachments/assets/140f314a-935b-439d-be3d-89cac0962df4" />

2. Cloud Infrastructure Architecture (AWS Architecture)
The system is designed entirely on AWS with high encapsulation, using VPCs divided into multiple separate subnets to isolate and secure data.

Public Subnet (10.0.0.0/24 & 10.0.6.0/24): Contains components that communicate with the Internet, including the Application Load Balancer (ALB) for the Dashboard, the Network Load Balancer (NLB) for the ML WebApp, the attack simulator server (EC2 Attacker), and the user simulator server (EC2 User Simulator).

Victim Private Subnet (10.0.1.0/24): Where the target Webserver (10.0.1.10) is located, running vulnerable web services and applications (DVWA, Weak SSH). Traffic here is mirrored via VXLAN on port 4789.

IDS Private Subnet (10.0.5.0/24): The heart of the analysis system, including the ECS Cluster running Fargate tasks (Dashboard and IDS Engine) and NIDS Sensor (10.0.5.10).

3. Traffic Collection and Preprocessing Pipeline
The data processing pipeline is designed to operate with minimal latency, meeting the requirements of a real-time system:

Traffic Mirroring: All TCP, UDP, and ICMP traffic from the Webserver is mirrored and forwarded to the NIDS Sensor via VXLAN using AWS Traffic Mirroring.

Decapsulation & Sensor: The NIDS Sensor uses the VXLAN bridge kernel (br-mirror) to remove the VXLAN shield. Next, the YAF tool will analyze the packet directly, extract 38 features, and convert them into JSON format via the super_mediator.

Data transmission: The collection script (collector.py) groups network streams into batches (10 flows) and sends them via HTTP POST to the IDS Engine API at a frequency of 2 seconds/time.

4. Artificial Intelligence Machine Learning Architecture (ML Architecture)
The core discovery model is a combination of several sophisticated deep learning methods, optimized using Domain Adaptation techniques:

Phase 1 - Feature Alignment: The system projects data from three different sources (NF-UQ, CIC-2017, and YAF Live) into a common 64-dimensional latent space using Feature Extractors combined with Invariant Risk Minimization (IRM) techniques.

Phase 2 - Base Models: After homogenization, the data is passed through three parallel base models:

CNN+LSTM: Extracts local spatial features and time series (~364K parameters).

TL-BiLSTM: Recognizes sequences using Temporal Attention mechanism.

Transformer: Exploits global context (4 layers, 8 heads).

Phase 3 & 4 - K-Fold Out-of-Fold & Meta-Learner: The system trains using the K-Fold Out-of-Fold strategy to obtain prediction probabilities, then feeds them into Meta-Learner (Logistic Regression) for final classification into 5 labels: Benign, BruteForce, DDoS, DoS, or Infiltration.

5. Simulation Environment
The system creates a dynamic network environment for continuous evaluation:

Attack (EC2 Attacker): Integrates automation tools via a Web interface (port 9000) to launch multi-stage scenarios: DDoS (HTTP Flood, TCP connect), DoS (Slowloris), BruteForce (SSH/HTTP), and Infiltration (Nmap recon, Lateral movement).

User Simulator: Simulates 9 distinct user behavior types (Personas) over ipvlan, from office workers (heavy/light HTTP), programmers (SSH, API), to IoT devices (periodic heartbeats), creating realistic platform traffic.

6. Monitoring & Auto-Response
Automatic Response: When the IDS Engine detects an attack sequence with a confidence level > 85% and records at least 3 alerts from the same IP address, the system will automatically update the Network ACL to completely block (DENY) the attacker's IP address at the network level.

Monitoring: The system has a real-time dashboard (React + TypeScript) that receives data from WebSocket. The infrastructure is monitored by CloudWatch, automatically configured to send email alerts via SNS when attack frequency increases or prediction latency is unusual.

Data Collection CI/CD: EventBridge activates Lambda to periodically collect labeled network data from the IDS Engine's Adaptation Buffer, compress it into gzip JSON, and import it into S3 for offline model retraining.

