import React from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import LiveTrafficChart from './components/LiveTrafficChart';
import DetectionReport from './components/DetectionReport';
import AlertTimelineOverlay from './components/AlertTimelineOverlay';
import ActiveBlocks from './components/ActiveBlocks';
import AlertFeed from './components/AlertFeed';
import SystemStatus from './components/SystemStatus';

export default function App() {
  const { connected, lastEvent, drainEvents } = useWebSocket();

  return (
    <div style={{ background: '#0f172a', minHeight: '100vh', color: '#e2e8f0', fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* Header */}
      <header style={{ padding: '16px 24px', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 24, fontWeight: 800 }}>NIDS Dashboard</span>
          <span style={{ fontSize: 12, color: '#94a3b8' }}>Network Intrusion Detection System</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            background: connected ? '#22c55e' : '#ef4444',
            display: 'inline-block',
          }} />
          <span style={{ fontSize: 12, color: connected ? '#22c55e' : '#ef4444' }}>
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </div>
      </header>

      {/* Main Grid */}
      <main style={{ padding: 24, display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, maxWidth: 1600, margin: '0 auto' }}>
        {/* Left column */}
        <div>
          <LiveTrafficChart drainEvents={drainEvents} />
          <AlertTimelineOverlay />
          <DetectionReport />
        </div>

        {/* Right column */}
        <div>
          <SystemStatus wsConnected={connected} />
          <ActiveBlocks lastEvent={lastEvent} />
          <AlertFeed lastEvent={lastEvent} />
        </div>
      </main>
    </div>
  );
}
