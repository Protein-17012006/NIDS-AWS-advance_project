export interface PredictionResult {
  predicted_class: string;
  confidence: number;
  probabilities: Record<string, number>;
  severity: string;
  latency_ms: number;
  timestamp: string;
}

export interface LivePredictionEvent {
  type: 'prediction' | 'alert';
  data: PredictionResult;
}

export interface AlertEvent {
  type: 'alert';
  severity: string;
  predicted_class: string;
  confidence: number;
  timestamp: string;
  message: string;
}



export interface AttackScheduleEntry {
  attack_type: string;
  start_time: string;
  end_time: string;
  attacker: string;
  status: string;
}

export interface MetricsResponse {
  total_predictions: number;
  class_counts: Record<string, number>;
  avg_latency_ms: number;
  avg_confidence: number;
  alerts_triggered: number;
  uptime_seconds: number;
}

export interface HealthResponse {
  status: string;
  models_loaded: boolean;
  uptime_seconds: number;
}



export const CLASS_COLORS: Record<string, string> = {
  Benign: '#22c55e',
  BruteForce: '#a855f7',
  DDoS: '#ef4444',
  DoS: '#f97316',
  Infiltration: '#eab308',
};

export const SEVERITY_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
};

export interface AttackResult {
  id: number;
  type: string;
  start_iso: string;
  end_iso: string;
  duration_sec: number;
  detected: boolean;
  time_to_detect_sec: number | null;
  first_detect_iso: string | null;
  alert_count: number;
  peak_confidence: number;
}

export interface DetectionReportResponse {
  attacks: AttackResult[];
  detection_rate: Record<string, number>;
  false_alarm_rate: number;
  false_alarm_count: number;
  benign_flow_count: number;
  benign_window_seconds: number;
  avg_ttd_sec: number | null;
  total_attacks: number;
  total_detected: number;
}
