import { DatasetInfo, ModelInfo, PredictResponse, CompareResponse } from '../types';

const BASE_URL = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getHealth: () => request<{ status: string; models_loaded: number; datasets_available: number }>('/health'),

  getDatasets: () => request<DatasetInfo[]>('/datasets'),

  getModels: () => request<ModelInfo[]>('/models'),

  predict: (dataset: string, model: string) =>
    request<PredictResponse>('/predict', {
      method: 'POST',
      body: JSON.stringify({ dataset, model }),
    }),

  compare: (dataset: string, models?: string[]) =>
    request<CompareResponse>('/compare', {
      method: 'POST',
      body: JSON.stringify({ dataset, models: models || [] }),
    }),

  updateSettings: (test_size: number, random_seed: number) =>
    request<{ test_size: number; random_seed: number; message: string }>('/settings', {
      method: 'PUT',
      body: JSON.stringify({ test_size, random_seed }),
    }),

  getSettings: () =>
    request<{ test_size: number; random_seed: number; message: string }>('/settings'),

  clearCache: () =>
    request<{ message: string }>('/cache', { method: 'DELETE' }),
};

// WebSocket connection for live prediction updates
export function createPredictionSocket(onMessage: (data: any) => void): WebSocket | null {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${proto}//${window.location.host}/ws/predictions`;
  try {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch { /* skip malformed */ }
    };
    ws.onerror = () => {};
    ws.onclose = () => {
      setTimeout(() => createPredictionSocket(onMessage), 3000);
    };
    return ws;
  } catch {
    return null;
  }
}
