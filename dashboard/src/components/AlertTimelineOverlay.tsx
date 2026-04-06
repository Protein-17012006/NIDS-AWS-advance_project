import React, { useEffect, useState, useMemo } from 'react';
import { getDetectionReport } from '../services/api';
import { DetectionReportResponse, CLASS_COLORS } from '../types';

export default function AlertTimelineOverlay() {
  const [report, setReport] = useState<DetectionReportResponse | null>(null);

  useEffect(() => {
    const fetch = () => {
      getDetectionReport().then(setReport).catch(() => {});
    };
    fetch();
    const id = setInterval(fetch, 5000);
    return () => clearInterval(id);
  }, []);

  const attacks = report?.attacks || [];

  // Auto-fit: if attacks exist, span from earliest start to max(latest end, now)
  // with 5% padding on each side. Otherwise default to last 10 min.
  const timeRange = useMemo(() => {
    const now = Date.now();
    if (attacks.length === 0) {
      return { start: now - 600_000, end: now };
    }
    const starts = attacks.map((a) => new Date(a.start_iso).getTime());
    const ends = attacks.map((a) => new Date(a.end_iso).getTime());
    const detects = attacks
      .filter((a) => a.first_detect_iso)
      .map((a) => new Date(a.first_detect_iso!).getTime());
    const minT = Math.min(...starts);
    const maxT = Math.max(...ends, ...detects, now);
    const span = maxT - minT || 600_000;
    const pad = span * 0.05;
    return { start: minT - pad, end: maxT + pad };
  }, [attacks]);

  const toPct = (isoOrMs: string | number) => {
    const t = typeof isoOrMs === 'string' ? new Date(isoOrMs).getTime() : isoOrMs;
    return Math.max(0, Math.min(100, ((t - timeRange.start) / (timeRange.end - timeRange.start)) * 100));
  };

  const fmtTime = (ms: number) => new Date(ms).toLocaleTimeString();

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h3 style={{ color: '#e2e8f0', margin: '0 0 12px' }}>
        Detection Timeline <span style={{ fontSize: 12, color: '#64748b', fontWeight: 400 }}>(last 10 min)</span>
      </h3>

      {/* Row 1: Ground Truth (scheduled attacks) */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, background: '#334155', borderRadius: 2, display: 'inline-block', border: '1px solid #64748b' }} />
          Ground Truth (scheduled)
        </div>
        <div style={{
          position: 'relative', height: 28, background: '#0f172a',
          borderRadius: 6, overflow: 'hidden',
        }}>
          {attacks.map((a, i) => {
            const left = toPct(a.start_iso);
            const right = toPct(a.end_iso);
            const width = Math.max(right - left, 0.5);
            const color = CLASS_COLORS[a.type] || '#94a3b8';
            return (
              <div
                key={`gt-${i}`}
                title={`${a.type}: ${new Date(a.start_iso).toLocaleTimeString()} → ${new Date(a.end_iso).toLocaleTimeString()}`}
                style={{
                  position: 'absolute', left: `${left}%`, width: `${width}%`,
                  height: '100%', background: color, opacity: 0.6,
                  borderRadius: 4, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 10, color: '#fff',
                  fontWeight: 600, overflow: 'hidden', whiteSpace: 'nowrap',
                }}
              >
                {width > 8 ? a.type : ''}
              </div>
            );
          })}
        </div>
      </div>

      {/* Row 2: Detections */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, background: '#22c55e', borderRadius: '50%', display: 'inline-block' }} />
          Detections (first alert)
        </div>
        <div style={{
          position: 'relative', height: 28, background: '#0f172a',
          borderRadius: 6, overflow: 'hidden',
        }}>
          {/* Light ground truth overlay for alignment reference */}
          {attacks.map((a, i) => {
            const left = toPct(a.start_iso);
            const right = toPct(a.end_iso);
            const width = Math.max(right - left, 0.5);
            const color = CLASS_COLORS[a.type] || '#94a3b8';
            return (
              <div
                key={`ref-${i}`}
                style={{
                  position: 'absolute', left: `${left}%`, width: `${width}%`,
                  height: '100%', background: color, opacity: 0.1,
                  borderRadius: 4,
                }}
              />
            );
          })}
          {/* Detection markers */}
          {attacks.map((a, i) => {
            if (!a.detected || !a.first_detect_iso) return null;
            const pos = toPct(a.first_detect_iso);
            const color = CLASS_COLORS[a.type] || '#22c55e';
            return (
              <div
                key={`det-${i}`}
                title={`${a.type} detected at ${new Date(a.first_detect_iso).toLocaleTimeString()} (TTD: ${a.time_to_detect_sec}s)`}
                style={{
                  position: 'absolute', left: `${pos}%`, top: '50%',
                  transform: 'translate(-50%, -50%)',
                  width: 14, height: 14, borderRadius: '50%',
                  background: color, border: '2px solid #fff',
                  cursor: 'pointer', zIndex: 2,
                  boxShadow: `0 0 6px ${color}`,
                }}
              />
            );
          })}
          {/* Missed attack indicators */}
          {attacks.filter((a) => !a.detected).map((a, i) => {
            const mid = (toPct(a.start_iso) + toPct(a.end_iso)) / 2;
            return (
              <div
                key={`miss-${i}`}
                title={`${a.type} MISSED`}
                style={{
                  position: 'absolute', left: `${mid}%`, top: '50%',
                  transform: 'translate(-50%, -50%)',
                  fontSize: 14, color: '#ef4444', fontWeight: 900,
                  zIndex: 2,
                }}
              >
                ✗
              </div>
            );
          })}
        </div>
      </div>

      {/* Time axis */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#64748b' }}>
        <span>{fmtTime(timeRange.start)}</span>
        <span>{fmtTime(timeRange.start + (timeRange.end - timeRange.start) * 0.25)}</span>
        <span>{fmtTime(timeRange.start + (timeRange.end - timeRange.start) * 0.5)}</span>
        <span>{fmtTime(timeRange.start + (timeRange.end - timeRange.start) * 0.75)}</span>
        <span>{fmtTime(timeRange.end)}</span>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
        {Object.entries(CLASS_COLORS).filter(([k]) => k !== 'Benign').map(([cls, color]) => (
          <div key={cls} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#94a3b8' }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: color, display: 'inline-block' }} />
            {cls}
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#94a3b8' }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#fff', display: 'inline-block', border: '2px solid #22c55e' }} />
          Detection point
        </div>
      </div>
    </div>
  );
}
