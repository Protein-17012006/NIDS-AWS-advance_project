const API_BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function getHealth() {
  return request<{ status: string; models_loaded: boolean; uptime_seconds: number }>('/health');
}

export async function getMetrics() {
  return request<{
    total_predictions: number;
    class_counts: Record<string, number>;
    avg_latency_ms: number;
    avg_confidence: number;
    alerts_triggered: number;
    uptime_seconds: number;
  }>('/metrics');
}

export async function getDetectionReport() {
  return request<import('../types').DetectionReportResponse>('/evaluation/detection-report');
}

export async function resetEvaluation() {
  return request<{ status: string; message: string }>('/evaluation/reset', { method: 'POST' });
}

/* ── Auto-Response / Active Blocks ── */

export interface BlockedEntry {
  ip: string;
  attack_class: string;
  confidence: number;
  rule_number: number;
  blocked_at: string;
}

export async function getBlockedIPs() {
  return request<{ enabled: boolean; blocked_ips: BlockedEntry[] }>('/response/blocked');
}

export async function unblockIP(ip: string) {
  return request<{ status: string; ip: string }>('/response/unblock', {
    method: 'POST',
    body: JSON.stringify({ ip }),
  });
}

export async function unblockAll() {
  return request<{ status: string; cleared: number }>('/response/unblock-all', { method: 'POST' });
}
