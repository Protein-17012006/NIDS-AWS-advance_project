"""Evaluation framework - ground truth alignment and per-attack metrics."""

import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional



class PredictionRecord:
    __slots__ = ('timestamp', 'src_ip', 'dst_ip', 'dst_port',
                 'predicted', 'ground_truth', 'rule', 'confidence')

    def __init__(self, timestamp: float, src_ip: str, dst_ip: str,
                 dst_port: int, predicted: str, ground_truth: str,
                 rule: str, confidence: float):
        self.timestamp = timestamp
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.predicted = predicted
        self.ground_truth = ground_truth
        self.rule = rule
        self.confidence = confidence


class AttackWindow:
    """A scheduled attack time window with ground truth label."""
    __slots__ = ('label', 'start', 'end', 'first_detect_time')

    def __init__(self, label: str, start: float, end: float):
        self.label = label
        self.start = start
        self.end = end
        self.first_detect_time: Optional[float] = None


class EvaluationTracker:
    """
    Tracks predictions against ground truth for live evaluation.

    Ground truth comes from the attack schedule (trigger API records
    start/end times). Predictions outside any attack window are Benign.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._records: List[PredictionRecord] = []
        self._attack_windows: List[AttackWindow] = []
        self._start_time = time.time()

    def reset(self):
        """Clear all recorded predictions and attack windows."""
        with self._lock:
            self._records.clear()
            self._attack_windows.clear()
            self._start_time = time.time()

    def add_attack_window(self, label: str, start: float, end: float):
        """Register an attack time window (called when attack is triggered)."""
        with self._lock:
            self._attack_windows.append(AttackWindow(label, start, end))

    def get_ground_truth(self, timestamp: float) -> str:
        """Look up ground truth for a timestamp based on attack schedule."""
        for aw in self._attack_windows:
            if aw.start <= timestamp <= aw.end:
                return aw.label
        return 'Benign'

    def record(self, timestamp: float, src_ip: str, dst_ip: str,
               dst_port: int, predicted: str, rule: str, confidence: float):
        """Record a single prediction with auto-assigned ground truth."""
        gt = self.get_ground_truth(timestamp)
        rec = PredictionRecord(
            timestamp=timestamp, src_ip=src_ip, dst_ip=dst_ip,
            dst_port=dst_port, predicted=predicted, ground_truth=gt,
            rule=rule, confidence=confidence,
        )
        with self._lock:
            self._records.append(rec)
            # Track time-to-detect
            if predicted == gt and gt != 'Benign':
                for aw in self._attack_windows:
                    if (aw.label == gt and aw.start <= timestamp <= aw.end
                            and aw.first_detect_time is None):
                        aw.first_detect_time = timestamp

    def compute_detection_report(self) -> Dict:
        """
        SOC-style detection report: per-attack-window metrics and false alarm
        rate during benign periods.

        Unlike per-flow confusion matrix, this evaluates at the *attack window*
        level: was the attack detected? How fast? How many alerts?
        False alarms are counted only during periods with NO attack scheduled.
        """
        now = time.time()
        with self._lock:
            recs = list(self._records)
            windows = list(self._attack_windows)

        # --- Per-attack-window metrics ---
        attacks = []
        for i, aw in enumerate(windows):
            # Count alerts that match this attack's label during its window
            window_alerts = [
                r for r in recs
                if aw.start <= r.timestamp <= aw.end and r.predicted == aw.label
            ]
            alert_count = len(window_alerts)
            peak_conf = max((r.confidence for r in window_alerts), default=0.0)
            detected = aw.first_detect_time is not None
            ttd = round(aw.first_detect_time - aw.start, 2) if detected else None

            attacks.append({
                'id': i,
                'type': aw.label,
                'start_iso': datetime.fromtimestamp(aw.start).isoformat(),
                'end_iso': datetime.fromtimestamp(aw.end).isoformat(),
                'duration_sec': round(aw.end - aw.start),
                'detected': detected,
                'time_to_detect_sec': ttd,
                'first_detect_iso': (
                    datetime.fromtimestamp(aw.first_detect_time).isoformat()
                    if detected else None
                ),
                'alert_count': alert_count,
                'peak_confidence': round(peak_conf, 4),
            })

        # --- Detection rate per attack type ---
        type_windows: Dict[str, List[Dict]] = defaultdict(list)
        for a in attacks:
            type_windows[a['type']].append(a)
        detection_rate = {}
        for atype, aws in type_windows.items():
            n_detected = sum(1 for a in aws if a['detected'])
            detection_rate[atype] = round(n_detected / len(aws), 4) if aws else 0.0

        # --- False alarm rate during clean benign windows ---
        # Only count false alarms in periods that are well-separated from
        # any attack window (CLEAN_GAP_SEC before first or after last).
        # This avoids counting residual attack traffic as false alarms.
        CLEAN_GAP_SEC = 30  # 1 aggregation epoch buffer

        def _near_any_window(ts: float) -> bool:
            for aw in windows:
                if (aw.start - CLEAN_GAP_SEC) <= ts <= (aw.end + CLEAN_GAP_SEC):
                    return True
            return False

        benign_recs = [r for r in recs if not _near_any_window(r.timestamp)]
        false_alarms = [r for r in benign_recs if r.predicted != 'Benign']
        false_alarm_count = len(false_alarms)
        benign_total = len(benign_recs)
        false_alarm_rate = (
            round(false_alarm_count / benign_total, 6)
            if benign_total > 0 else 0.0
        )

        # Benign window duration estimate
        total_attack_sec = sum(aw.end - aw.start + 2 * CLEAN_GAP_SEC
                               for aw in windows)
        uptime = now - self._start_time
        benign_window_sec = max(0, uptime - total_attack_sec)

        # --- Aggregate stats ---
        total_attacks = len(windows)
        total_detected = sum(1 for a in attacks if a['detected'])
        ttd_values = [a['time_to_detect_sec'] for a in attacks
                      if a['time_to_detect_sec'] is not None]
        avg_ttd = round(sum(ttd_values) / len(ttd_values), 2) if ttd_values else None

        return {
            'attacks': attacks,
            'detection_rate': detection_rate,
            'false_alarm_rate': false_alarm_rate,
            'false_alarm_count': false_alarm_count,
            'benign_flow_count': benign_total,
            'benign_window_seconds': round(benign_window_sec, 1),
            'avg_ttd_sec': avg_ttd,
            'total_attacks': total_attacks,
            'total_detected': total_detected,
        }
