"""
Feature pipeline — converts raw YAF IPFIX flows into model-ready windows.

Design principles (matching training pipeline in feature_alignment.py):
1. Keep ALL raw YAF features as-is — NO mapping to UQ schema, NO zero-filling
2. Session grouping by (src_ip, dst_ip, dst_port) — separates attack/benign flows
3. Sliding window: size=30, stride=10, zero-pad sessions < 30 flows
"""

import numpy as np
from sklearn.preprocessing import StandardScaler

from .config import WINDOW_SIZE, STRIDE, YAF_FEATURE_NAMES

# TCP flag character → bitmask (for super_mediator string output like "APF")
_TCP_FLAG_MAP = {
    'F': 0x01, 'S': 0x02, 'R': 0x04, 'P': 0x08,
    'A': 0x10, 'U': 0x20, 'E': 0x40, 'C': 0x80,
}
_TCP_FLAG_FIELDS = {
    'initialTCPFlags', 'unionTCPFlags',
    'reverseInitialTCPFlags', 'reverseUnionTCPFlags',
}
_FLOW_END_REASON_MAP = {
    'idle': 1, 'active': 2, 'end': 3, 'forced': 4, 'lack': 5,
}


def _to_numeric(name: str, val) -> float:
    """Convert a YAF field value to float, handling string TCP flags and enums."""
    if val is None or val == '':
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if name in _TCP_FLAG_FIELDS and isinstance(val, str):
        n = 0
        for c in val:
            n |= _TCP_FLAG_MAP.get(c, 0)
        return float(n)
    if name == 'flowEndReason' and isinstance(val, str):
        return float(_FLOW_END_REASON_MAP.get(val.lower().strip(), 0))
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


class FlowWindowBuffer:
    """
    Maintains sliding-window buffers per flow session.

    Session key = f"{src_ip}_{dst_ip}_{dst_port}" to separate flows by IP pair.
    This ensures attack flows from the attacker IP are grouped separately
    from benign background traffic.

    When a buffer accumulates WINDOW_SIZE flows, it yields a window
    and advances by STRIDE.
    """

    def __init__(self, window_size=WINDOW_SIZE, stride=STRIDE, max_sessions=10000):
        self.window_size = window_size
        self.stride = stride
        self.max_sessions = max_sessions
        # session_key -> {'flows': list[np.ndarray], 'emitted': int}
        self._buffers: dict[str, dict] = {}

    @staticmethod
    def make_key(src_ip: str, dst_ip: str, dst_port: int) -> str:
        """Session key groups by IP pair + dst port."""
        return f"{src_ip}_{dst_ip}_{int(dst_port)}"

    def add_flow(self, flow_features: np.ndarray,
                 src_ip: str, dst_ip: str,
                 src_port: int, dst_port: int) -> list[np.ndarray]:
        """
        Add a flow to the appropriate session buffer.

        Returns list of ready windows (may be empty or contain multiple).
        Each window is shape (window_size, n_features).
        """
        key = self.make_key(src_ip, dst_ip, dst_port)

        if key not in self._buffers:
            if len(self._buffers) >= self.max_sessions:
                oldest = next(iter(self._buffers))
                del self._buffers[oldest]
            self._buffers[key] = {'flows': [], 'emitted': 0}

        buf = self._buffers[key]
        buf['flows'].append(flow_features)

        ready_windows = []
        n_flows = len(buf['flows'])

        while buf['emitted'] * self.stride + self.window_size <= n_flows:
            start = buf['emitted'] * self.stride
            window = np.array(buf['flows'][start:start + self.window_size],
                              dtype=np.float32)
            ready_windows.append(window)
            buf['emitted'] += 1

        return ready_windows

    def get_partial_window(self, src_ip: str, dst_ip: str,
                            src_port: int, dst_port: int) -> np.ndarray | None:
        """
        Get zero-padded partial window for early prediction.
        Returns (window_size, n_features) or None if buffer empty.
        Matches training behavior: sessions < 30 flows are zero-padded.
        """
        key = self.make_key(src_ip, dst_ip, dst_port)
        if key not in self._buffers or not self._buffers[key]['flows']:
            return None

        flows = self._buffers[key]['flows']
        n_features = flows[0].shape[0]
        window = np.zeros((self.window_size, n_features), dtype=np.float32)
        n = min(len(flows), self.window_size)
        window[:n] = np.array(flows[-n:], dtype=np.float32)
        return window

    def clear(self):
        self._buffers.clear()

    @property
    def session_count(self) -> int:
        return len(self._buffers)


def parse_yaf_flow(record: dict) -> np.ndarray:
    """
    Extract raw YAF features from a flow record.

    Reads each field in YAF_FEATURE_NAMES order.
    flowDurationMilliseconds is computed from flowStart/End if not present.
    All features kept as-is — no mapping, no zero-filling to another schema.

    Args:
        record: dict with YAF IPFIX field names (from super_mediator JSON)

    Returns:
        features: np.ndarray (YAF_INPUT_DIM,) float32
    """
    features = np.zeros(len(YAF_FEATURE_NAMES), dtype=np.float32)

    for i, name in enumerate(YAF_FEATURE_NAMES):
        if name == 'flowDurationMilliseconds':
            # Compute from timestamps if not directly present
            if name in record:
                features[i] = _to_numeric(name, record[name])
            else:
                t_start = record.get('flowStartMilliseconds', 0)
                t_end = record.get('flowEndMilliseconds', 0)
                try:
                    features[i] = max(0.0, float(t_end) - float(t_start))
                except (ValueError, TypeError):
                    features[i] = 0.0
        elif name in record:
            features[i] = _to_numeric(name, record[name])

    return features


def extract_ports(record: dict) -> tuple[int, int]:
    """Extract source and destination transport ports from a YAF flow record."""
    src_port = int(record.get('sourceTransportPort', 0))
    dst_port = int(record.get('destinationTransportPort', 0))
    return src_port, dst_port


class FlowFeaturePipeline:
    """
    Complete pipeline: raw YAF flow dict -> scaled feature windows.

    Usage:
        pipeline = FlowFeaturePipeline(scaler)
        for flow in incoming_flows:
            windows = pipeline.process_flow(flow)
            for w in windows:
                prediction = engine.predict_window(w)
    """

    def __init__(self, scaler: StandardScaler | None = None):
        self.scaler = scaler
        self.buffer = FlowWindowBuffer()

    def process_flow(self, flow: dict) -> list[np.ndarray]:
        """
        Process a single YAF flow record.

        Returns list of ready windows, each shape (WINDOW_SIZE, YAF_INPUT_DIM),
        already scaled if a scaler is available.
        """
        features = parse_yaf_flow(flow)
        src_port, dst_port = extract_ports(flow)
        src_ip = str(flow.get("sourceIPv4Address", flow.get("src_ip", "0.0.0.0")))
        dst_ip = str(flow.get("destinationIPv4Address", flow.get("dst_ip", "0.0.0.0")))

        raw_windows = self.buffer.add_flow(features, src_ip, dst_ip, src_port, dst_port)

        if self.scaler is None:
            return raw_windows

        scaled_windows = []
        for w in raw_windows:
            scaled = self.scaler.transform(w).astype(np.float32)
            scaled_windows.append(scaled)

        return scaled_windows

    @property
    def session_count(self) -> int:
        return self.buffer.session_count
