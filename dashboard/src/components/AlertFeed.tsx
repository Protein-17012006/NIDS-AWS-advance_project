import React, { useEffect, useRef, useState } from 'react';
import { LivePredictionEvent, SEVERITY_COLORS } from '../types';

interface Alert {
  id: number;
  timestamp: string;
  severity: string;
  predicted_class: string;
  confidence: number;
}

interface Props {
  lastEvent: LivePredictionEvent | null;
}

let alertCounter = 0;

export default function AlertFeed({ lastEvent }: Props) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!lastEvent?.data) return;
    const d = lastEvent.data;
    if (d.predicted_class === 'Benign') return;

    const newAlert: Alert = {
      id: ++alertCounter,
      timestamp: d.timestamp || new Date().toISOString(),
      severity: d.severity || 'medium',
      predicted_class: d.predicted_class,
      confidence: d.confidence,
    };

    setAlerts((prev) => [newAlert, ...prev].slice(0, 200));
  }, [lastEvent]);

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h3 style={{ color: '#e2e8f0', margin: '0 0 12px' }}>
        Alert Feed
        <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 8 }}>
          ({alerts.length} alerts)
        </span>
      </h3>
      <div
        ref={containerRef}
        style={{ maxHeight: 300, overflowY: 'auto', fontSize: 13 }}
      >
        {alerts.length === 0 ? (
          <p style={{ color: '#64748b' }}>No attacks detected yet…</p>
        ) : (
          alerts.map((a) => (
            <div
              key={a.id}
              style={{
                padding: '6px 10px',
                marginBottom: 4,
                borderRadius: 6,
                borderLeft: `4px solid ${SEVERITY_COLORS[a.severity] || '#eab308'}`,
                background: '#0f172a',
                color: '#e2e8f0',
              }}
            >
              <span style={{ color: '#94a3b8', fontSize: 11 }}>
                {new Date(a.timestamp).toLocaleTimeString()}
              </span>{' '}
              <span
                style={{
                  fontWeight: 700,
                  color: SEVERITY_COLORS[a.severity] || '#eab308',
                  textTransform: 'uppercase',
                  fontSize: 11,
                }}
              >
                [{a.severity}]
              </span>{' '}
              <strong>{a.predicted_class}</strong> detected — confidence:{' '}
              {(a.confidence * 100).toFixed(1)}%
            </div>
          ))
        )}
      </div>
    </div>
  );
}
