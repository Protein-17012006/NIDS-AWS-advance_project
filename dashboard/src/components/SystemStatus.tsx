import React, { useEffect, useState } from 'react';
import { getHealth, getMetrics } from '../services/api';

interface ComponentStatus {
  name: string;
  status: 'ok' | 'degraded' | 'down';
  detail?: string;
}

export default function SystemStatus({ wsConnected }: { wsConnected: boolean }) {
  const [components, setComponents] = useState<ComponentStatus[]>([]);

  useEffect(() => {
    const check = async () => {
      const statuses: ComponentStatus[] = [];

      // IDS Engine health
      try {
        const h = await getHealth();
        statuses.push({
          name: 'IDS Engine',
          status: h.models_loaded ? 'ok' : 'degraded',
          detail: h.models_loaded ? `Up ${Math.round(h.uptime_seconds)}s` : 'Models not loaded',
        });
      } catch {
        statuses.push({ name: 'IDS Engine', status: 'down', detail: 'Unreachable' });
      }

      // WebSocket
      statuses.push({
        name: 'WebSocket',
        status: wsConnected ? 'ok' : 'down',
        detail: wsConnected ? 'Connected' : 'Disconnected',
      });

      // Metrics (proxy for capture worker)
      try {
        const m = await getMetrics();
        statuses.push({
          name: 'Flow Pipeline',
          status: m.total_predictions > 0 ? 'ok' : 'degraded',
          detail: `${m.total_predictions} predictions processed`,
        });
      } catch {
        statuses.push({ name: 'Flow Pipeline', status: 'down', detail: 'No data' });
      }

      setComponents(statuses);
    };
    check();
    const id = setInterval(check, 15000);
    return () => clearInterval(id);
  }, [wsConnected]);

  const statusColor: Record<string, string> = {
    ok: '#22c55e',
    degraded: '#f59e0b',
    down: '#ef4444',
  };

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h3 style={{ color: '#e2e8f0', margin: '0 0 12px' }}>System Status</h3>
      {components.map((c) => (
        <div
          key={c.name}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 0',
            borderBottom: '1px solid #334155',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: statusColor[c.status],
                display: 'inline-block',
              }}
            />
            <span style={{ color: '#e2e8f0', fontSize: 13 }}>{c.name}</span>
          </div>
          <span style={{ color: '#94a3b8', fontSize: 12 }}>{c.detail}</span>
        </div>
      ))}
    </div>
  );
}
