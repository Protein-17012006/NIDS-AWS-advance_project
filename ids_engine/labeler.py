"""Ground Truth Labeler — automatic labeling from attack schedule."""

import threading
import time
from datetime import datetime
import numpy as np

from .config import UNIFIED_CLASSES, ADAPTATION_BUFFER_MAX_WINDOWS


class GroundTruthLabeler:
    """
    Maintains an attack schedule and computes evaluation metrics.

    The schedule is a list of time intervals with associated ground truth class.
    Predictions are matched to the schedule by timestamp.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._schedule: list[dict] = []
        self._predictions: list[dict] = []  # {timestamp, predicted, ground_truth}
        self._window_seconds = 300  # rolling window for metrics

        # Adaptation buffer: stores (window, label) pairs for meta-learner retraining
        self._adaptation_windows: list[np.ndarray] = []
        self._adaptation_labels: list[int] = []
        self._class_to_idx = {c: i for i, c in enumerate(UNIFIED_CLASSES)}

    def add_schedule_entry(self, attack_class: str, attacker: str,
                           start: datetime, end: datetime,
                           attacker_ip: str = ''):
        """Add a single entry to the schedule (used when triggering attacks)."""
        entry = {
            'start': start.strftime('%H:%M:%S'),
            'end': end.strftime('%H:%M:%S'),
            'class': attack_class,
            'attacker': attacker,
            'attacker_ip': attacker_ip,
            'start_dt': start,
            'end_dt': end,
        }
        with self._lock:
            self._schedule.append(entry)

    def get_ground_truth(self, timestamp: datetime,
                         src_ip: str = '', dst_ip: str = '') -> str:
        """
        Look up ground truth class for a given timestamp and IP pair.

        IP-based labeling: labels a flow as attack ONLY if:
          1. Timestamp falls within an attack window, AND
          2. src_ip OR dst_ip matches the known attacker IP for that window
             (bidirectional: attacker→victim AND victim→attacker traffic)

        If attacker_ip is empty in the schedule entry (legacy), falls back to
        time-only labeling.
        """
        t_str = timestamp.strftime('%H:%M:%S')
        with self._lock:
            for entry in self._schedule:
                if entry['start'] <= t_str <= entry['end']:
                    attacker_ip = entry.get('attacker_ip', '')
                    if not attacker_ip:
                        # Legacy: time-only labeling
                        return entry['class']
                    # Bidirectional: label if src_ip or dst_ip matches attacker
                    if src_ip and src_ip == attacker_ip:
                        return entry['class']
                    if dst_ip and dst_ip == attacker_ip:
                        return entry['class']
        return 'Benign'  # Default when no attack scheduled or IP doesn't match

    def record_prediction(self, timestamp: datetime, predicted_class: str,
                          src_ip: str = '', dst_ip: str = ''):
        """Record a prediction with its ground truth label."""
        gt = self.get_ground_truth(timestamp, src_ip=src_ip, dst_ip=dst_ip)
        with self._lock:
            self._predictions.append({
                'timestamp': timestamp,
                'predicted': predicted_class,
                'ground_truth': gt,
            })

    def get_schedule(self) -> list[dict]:
        with self._lock:
            return [
                {
                    'attack_type': e['class'],
                    'start_time': e['start'],
                    'end_time': e['end'],
                    'attacker': e.get('attacker', ''),
                    'status': 'completed'
                    if datetime.now().strftime('%H:%M:%S') > e['end']
                    else 'active',
                }
                for e in self._schedule
            ]

    # ============================================================
    # ADAPTATION BUFFER
    # ============================================================

    def buffer_labeled_window(self, window: np.ndarray, timestamp: datetime,
                              src_ip: str = '', dst_ip: str = ''):
        """
        Buffer a feature window with its ground truth label (from attack schedule).
        Uses IP-based labeling: only labels as attack if src_ip matches attacker.
        Also buffers some Benign windows to maintain class balance.
        """
        gt = self.get_ground_truth(timestamp, src_ip=src_ip, dst_ip=dst_ip)
        label_idx = self._class_to_idx.get(gt, 0)

        with self._lock:
            if len(self._adaptation_windows) >= ADAPTATION_BUFFER_MAX_WINDOWS:
                return  # Buffer full

            # Buffer ALL windows (both attack and benign) for balanced training
            self._adaptation_windows.append(window.copy())
            self._adaptation_labels.append(label_idx)

    def get_adaptation_data(self) -> dict:
        """Export buffered labeled windows for adaptation."""
        with self._lock:
            if not self._adaptation_windows:
                return {'windows': [], 'labels': [], 'n_samples': 0, 'class_distribution': {}}

            windows = np.array(self._adaptation_windows)
            labels = np.array(self._adaptation_labels)

            dist = {}
            for i, cls in enumerate(UNIFIED_CLASSES):
                dist[cls] = int(np.sum(labels == i))

            return {
                'windows': windows,
                'labels': labels,
                'n_samples': len(labels),
                'class_distribution': dist,
            }

    def get_adaptation_stats(self) -> dict:
        """Return stats about buffered adaptation data without the actual data."""
        with self._lock:
            if not self._adaptation_labels:
                return {'n_samples': 0, 'class_distribution': {}}

            labels = np.array(self._adaptation_labels)
            dist = {}
            for i, cls in enumerate(UNIFIED_CLASSES):
                dist[cls] = int(np.sum(labels == i))

            return {
                'n_samples': len(labels),
                'class_distribution': dist,
            }

    def clear_adaptation_buffer(self):
        """Clear the adaptation buffer after successful retraining."""
        with self._lock:
            self._adaptation_windows.clear()
            self._adaptation_labels.clear()

    def load_adaptation_from_npz(self, windows: np.ndarray, labels: np.ndarray):
        """Load pre-collected training data into the adaptation buffer."""
        with self._lock:
            for w, l in zip(windows, labels):
                self._adaptation_windows.append(w.copy())
                self._adaptation_labels.append(int(l))
