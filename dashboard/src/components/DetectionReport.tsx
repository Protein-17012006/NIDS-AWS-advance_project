import React, { useEffect, useState } from 'react';
import { getDetectionReport, resetEvaluation } from '../services/api';
import { DetectionReportResponse, AttackResult, CLASS_COLORS } from '../types';

export default function DetectionReport() {
  const [report, setReport] = useState<DetectionReportResponse | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchReport = () => {
    getDetectionReport().then(setReport).catch(() => {});
  };

  const handleRefresh = () => {
    setRefreshing(true);
    resetEvaluation()
      .then(() => getDetectionReport())
      .then(setReport)
      .catch(() => {})
      .finally(() => setTimeout(() => setRefreshing(false), 300));
  };

  useEffect(() => {
    fetchReport();
    const id = setInterval(fetchReport, 10000);
    return () => clearInterval(id);
  }, []);

  if (!report) {
    return (
      <div style={{ background: '#1e293b', borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <h3 style={{ color: '#e2e8f0', margin: 0 }}>Detection Report</h3>
        <p style={{ color: '#94a3b8', marginTop: 8 }}>Waiting for data…</p>
      </div>
    );
  }

  const { attacks, detection_rate, false_alarm_rate, false_alarm_count,
    benign_flow_count, avg_ttd_sec, total_attacks, total_detected } = report;

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ color: '#e2e8f0', margin: 0 }}>Detection Report</h3>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            background: refreshing ? '#334155' : '#3b82f6',
            color: '#fff', border: 'none', borderRadius: 6,
            padding: '6px 14px', fontSize: 12, fontWeight: 600,
            cursor: refreshing ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s',
          }}
        >
          {refreshing ? '↻ Resetting…' : '↻ Reset & Refresh'}
        </button>
      </div>

      {/* Summary bar */}
      <SummaryBar
        totalAttacks={total_attacks}
        totalDetected={total_detected}
        avgTtd={avg_ttd_sec}
        falseAlarmCount={false_alarm_count}
        benignFlows={benign_flow_count}
        falseAlarmRate={false_alarm_rate}
      />

      {/* Detection rate gauges */}
      {Object.keys(detection_rate).length > 0 && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          {Object.entries(detection_rate).map(([atype, rate]) => (
            <DetectionGauge key={atype} label={atype} rate={rate} />
          ))}
        </div>
      )}

      {/* Per-attack cards */}
      {attacks.length === 0 ? (
        <p style={{ color: '#64748b', fontSize: 13 }}>No attacks detected yet. Waiting for attack schedule from the simulator.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {attacks.map((a) => (
            <AttackCard key={a.id} attack={a} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ---- Summary Bar ---- */
function SummaryBar({ totalAttacks, totalDetected, avgTtd, falseAlarmCount, benignFlows, falseAlarmRate }: {
  totalAttacks: number; totalDetected: number; avgTtd: number | null;
  falseAlarmCount: number; benignFlows: number; falseAlarmRate: number;
}) {
  const allDetected = totalAttacks > 0 && totalDetected === totalAttacks;
  const detectColor = totalAttacks === 0 ? '#94a3b8' : allDetected ? '#22c55e' : '#f97316';
  const faColor = falseAlarmCount === 0 ? '#22c55e' : '#ef4444';

  return (
    <div style={{
      display: 'flex', gap: 16, marginBottom: 16, padding: 12,
      background: '#0f172a', borderRadius: 8, flexWrap: 'wrap',
      justifyContent: 'space-around',
    }}>
      <StatBox
        value={totalAttacks > 0 ? `${totalDetected}/${totalAttacks}` : '—'}
        label="Attacks Detected"
        color={detectColor}
      />
      <StatBox
        value={avgTtd !== null ? `${avgTtd}s` : '—'}
        label="Avg Time-to-Detect"
        color={avgTtd !== null && avgTtd < 30 ? '#22c55e' : '#f97316'}
      />
      <StatBox
        value={String(falseAlarmCount)}
        label={`False Alarms / ${benignFlows.toLocaleString()} flows`}
        color={faColor}
      />
      <StatBox
        value={`${(falseAlarmRate * 100).toFixed(2)}%`}
        label="False Alarm Rate"
        color={faColor}
      />
    </div>
  );
}

function StatBox({ value, label, color }: { value: string; label: string; color: string }) {
  return (
    <div style={{ textAlign: 'center', minWidth: 90 }}>
      <div style={{ fontSize: 22, fontWeight: 800, color }}>{value}</div>
      <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>{label}</div>
    </div>
  );
}

/* ---- Detection Rate Gauge ---- */
function DetectionGauge({ label, rate }: { label: string; rate: number }) {
  const pct = Math.round(rate * 100);
  const color = CLASS_COLORS[label] || '#94a3b8';
  return (
    <div style={{ textAlign: 'center', flex: '1 1 70px' }}>
      <div style={{
        width: 52, height: 52, borderRadius: '50%',
        background: `conic-gradient(${color} ${pct * 3.6}deg, #334155 0deg)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        margin: '0 auto 4px',
      }}>
        <span style={{
          background: '#1e293b', borderRadius: '50%', width: 38, height: 38,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 700, color,
        }}>
          {pct}%
        </span>
      </div>
      <div style={{ fontSize: 10, color: '#94a3b8' }}>{label}</div>
    </div>
  );
}

/* ---- Per-Attack Card ---- */
function AttackCard({ attack }: { attack: AttackResult }) {
  const a = attack;
  const color = CLASS_COLORS[a.type] || '#94a3b8';
  const startTime = new Date(a.start_iso).toLocaleTimeString();
  const endTime = new Date(a.end_iso).toLocaleTimeString();

  // TTD bar: how far into the attack window was detection?
  const ttdPct = a.detected && a.time_to_detect_sec !== null
    ? Math.min(100, (a.time_to_detect_sec / a.duration_sec) * 100)
    : 0;

  return (
    <div style={{
      background: '#0f172a', borderRadius: 8, padding: 12,
      borderLeft: `4px solid ${color}`,
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{
          background: color, color: '#fff', padding: '2px 8px',
          borderRadius: 4, fontSize: 11, fontWeight: 700,
        }}>
          {a.type}
        </span>
        <span style={{
          color: a.detected ? '#22c55e' : '#ef4444',
          fontSize: 12, fontWeight: 700,
        }}>
          {a.detected ? '✓ Detected' : '✗ Missed'}
        </span>
        <span style={{ color: '#64748b', fontSize: 11, marginLeft: 'auto' }}>
          {startTime} → {endTime}
        </span>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 16, fontSize: 12, color: '#94a3b8', marginBottom: 8 }}>
        <span>TTD: <b style={{ color: a.detected ? '#22c55e' : '#64748b' }}>
          {a.time_to_detect_sec !== null ? `${a.time_to_detect_sec}s` : '—'}
        </b></span>
        <span>Alerts: <b style={{ color: '#e2e8f0' }}>{a.alert_count.toLocaleString()}</b></span>
        <span>Severity: <b style={{ color: '#e2e8f0' }}>{(a.peak_confidence * 100).toFixed(0)}%</b></span>
        <span>Duration: <b style={{ color: '#e2e8f0' }}>{a.duration_sec}s</b></span>
      </div>

      {/* TTD timeline bar */}
      <div style={{
        height: 6, background: '#334155', borderRadius: 3,
        overflow: 'hidden', position: 'relative',
      }}>
        {/* Full attack window */}
        <div style={{
          position: 'absolute', top: 0, left: 0, height: '100%',
          width: '100%', background: `${color}22`,
        }} />
        {/* Detection point */}
        {a.detected && (
          <div style={{
            position: 'absolute', top: -1, left: `${ttdPct}%`,
            width: 8, height: 8, borderRadius: '50%',
            background: '#22c55e', border: '2px solid #0f172a',
            transform: 'translateX(-50%)',
          }} />
        )}
        {/* Progress to detection */}
        {a.detected && (
          <div style={{
            position: 'absolute', top: 0, left: 0, height: '100%',
            width: `${ttdPct}%`, background: `${color}66`,
            borderRadius: 3,
          }} />
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#64748b', marginTop: 2 }}>
        <span>Attack Start</span>
        <span>Attack End</span>
      </div>
    </div>
  );
}
