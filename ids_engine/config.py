"""Configuration constants for the IDS Engine."""

import os

# ============================================================
# PATH CONFIGURATION
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default model directory (IRM version)
MODEL_DIR = os.environ.get(
    "IDS_MODEL_DIR",
    os.path.join(BASE_DIR, "Project", "Model", "Model_IRM"),
)

# S3 model path (used when running on AWS)
S3_MODEL_BUCKET = os.environ.get("IDS_S3_BUCKET", "")
S3_MODEL_PREFIX = os.environ.get("IDS_S3_MODEL_PREFIX", "models/")

# ============================================================
# MODEL HYPERPARAMETERS (must match training)
# ============================================================
LATENT_DIM = 64
WINDOW_SIZE = 30
STRIDE = 10
NUM_CLASSES = 5
UNIFIED_CLASSES = ['Benign', 'BruteForce', 'DDoS', 'DoS', 'Infiltration']

# Base model names in load order
BASE_MODEL_NAMES = ['cnn_lstm', 'tl_bilstm', 'transformer']

# Model weight filenames
MODEL_FILES = {
    'cnn_lstm': 'final_cnn_lstm.pth',
    'tl_bilstm': 'final_tl_bilstm.pth',
    'transformer': 'final_transformer.pth',
}
META_LEARNER_FILE = 'meta_learner_lr.pkl'
SCALER_UQ_FILE = 'scaler_uq.pkl'
SCALER_YAF_FILE = 'scaler_yaf.pkl'

# Feature dimensions (must match training data)
UQ_INPUT_DIM = 47
CIC_INPUT_DIM = 78

# ============================================================
# YAF FEATURE SCHEMA (raw IPFIX fields from YAF 3.x --flow-stats)
# These are the numeric features extracted in order from each flow.
# Domain adaptation handles the mapping to shared latent space;
# NO zero-filling or mapping to UQ schema.
# ============================================================
YAF_FEATURE_NAMES = [
    # --- Basic flow record ---
    'protocolIdentifier',           # IP protocol (6=TCP, 17=UDP, ...)
    'flowDurationMilliseconds',     # derived: flowEnd - flowStart
    'octetTotalCount',              # forward bytes
    'reverseOctetTotalCount',       # backward bytes
    'packetTotalCount',             # forward packets
    'reversePacketTotalCount',      # backward packets
    'flowAttributes',               # fwd flow attribute flags
    'reverseFlowAttributes',        # rev flow attribute flags
    'reverseFlowDeltaMilliseconds', # RTT approximation
    'ipClassOfService',             # ToS / DSCP forward
    'reverseIpClassOfService',      # ToS / DSCP reverse
    'silkAppLabel',                 # L7 protocol (with --applabel)
    'flowEndReason',                # why flow ended
    # --- TCP flags (from subTemplateMultiList, flattened by super_mediator) ---
    'initialTCPFlags',              # TCP flags of first fwd packet
    'unionTCPFlags',                # union of remaining fwd TCP flags
    'reverseInitialTCPFlags',       # TCP flags of first rev packet
    'reverseUnionTCPFlags',         # union of remaining rev TCP flags
    'tcpUrgTotalCount',             # fwd urgent packets
    'reverseTcpUrgTotalCount',      # rev urgent packets
    # --- Flow statistics (--flow-stats) forward ---
    'dataByteCount',                # fwd payload bytes only
    'averageInterarrivalTime',      # fwd avg IAT (ms)
    'standardDeviationInterarrivalTime',  # fwd stddev IAT
    'smallPacketCount',             # fwd packets < 60 bytes payload
    'nonEmptyPacketCount',          # fwd packets with payload
    'largePacketCount',             # fwd packets > 225 bytes payload
    'firstNonEmptyPacketSize',      # fwd first payload length
    'maxPacketSize',                # fwd max payload length
    'standardDeviationPayloadLength',     # fwd stddev payload
    'firstEightNonEmptyPacketDirections', # directionality byte
    # --- Flow statistics (--flow-stats) reverse ---
    'reverseDataByteCount',         # rev payload bytes only
    'reverseAverageInterarrivalTime',     # rev avg IAT (ms)
    'reverseStandardDeviationInterarrivalTime',  # rev stddev IAT
    'reverseSmallPacketCount',      # rev packets < 60 bytes payload
    'reverseNonEmptyPacketCount',   # rev packets with payload
    'reverseLargePacketCount',      # rev packets > 225 bytes payload
    'reverseFirstNonEmptyPacketSize',     # rev first payload length
    'reverseMaxPacketSize',         # rev max payload length
    'reverseStandardDeviationPayloadLength',  # rev stddev payload
]

YAF_INPUT_DIM = len(YAF_FEATURE_NAMES)  # 38

# ============================================================
# INFERENCE SETTINGS
# ============================================================
INFERENCE_BATCH_SIZE = 512
DEFAULT_DATASET_TYPE = 'yaf'  # live traffic from YAF IPFIX

# Severity mapping for alerts
SEVERITY_MAP = {
    'Benign': 'info',
    'DDoS': 'critical',
    'DoS': 'high',
    'BruteForce': 'high',
    'Infiltration': 'critical',
}

# Temperature scaling (default T=1.0 means no scaling)
DEFAULT_TEMPERATURE = 1.0

# Adaptation buffer limits
ADAPTATION_BUFFER_MAX_WINDOWS = 50000

# ============================================================
# AWS CONFIGURATION
# ============================================================
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
CLOUDWATCH_NAMESPACE = "NIDS/Predictions"
SNS_TOPIC_ARN = os.environ.get("IDS_SNS_TOPIC_ARN", "")

# Attacker IP (set via environment from ECS task definition)
ATTACKER_IP = os.environ.get("ATTACKER_IP", "10.0.0.10")
