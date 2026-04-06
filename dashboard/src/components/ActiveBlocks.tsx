import React, { useState, useEffect, useCallback } from 'react';
import { getBlockedIPs, unblockIP, unblockAll, BlockedEntry } from '../services/api';

interface Props {
  lastEvent: any;
}

export default function ActiveBlocks({ lastEvent }: Props) {
  const [blocked, setBlocked] = useState<BlockedEntry[]>([]);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await getBlockedIPs();
      setBlocked(data.blocked_ips || []);
      setEnabled(data.enabled ?? false);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  }, [refresh]);

  // React to auto_block / unblock events
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.type === 'auto_block' || lastEvent.type === 'unblock' || lastEvent.type === 'unblock_all') {
      refresh();
    }
  }, [lastEvent, refresh]);

  const handleUnblock = async (ip: string) => {
    try {
      await unblockIP(ip);
      refresh();
    } catch {}
  };

  const handleUnblockAll = async () => {
    setLoading(true);
    try {
      await unblockAll();
      refresh();
    } catch {} finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      background: '#1e293b', borderRadius: 12, padding: 16,
      border: blocked.length > 0 ? '1px solid #dc2626' : '1px solid #334155',
      marginBottom: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#e2e8f0' }}>
          Active Blocks
          {blocked.length > 0 && (
            <span style={{
              marginLeft: 8, padding: '2px 8px', borderRadius: 10,
              background: '#dc2626', color: '#fff', fontSize: 11,
            }}>
              {blocked.length}
            </span>
          )}
        </h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{
            fontSize: 11, color: enabled ? '#22c55e' : '#94a3b8',
          }}>
            {enabled ? 'Auto-response ON' : 'Auto-response OFF'}
          </span>
          {blocked.length > 0 && (
            <button
              onClick={handleUnblockAll}
              disabled={loading}
              style={{
                padding: '4px 10px', borderRadius: 6, border: '1px solid #475569',
                background: '#0f172a', color: '#f87171', fontSize: 11,
                cursor: 'pointer', fontWeight: 500,
              }}
            >
              Unblock All
            </button>
          )}
        </div>
      </div>

      {blocked.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '16px 0', color: '#64748b', fontSize: 13 }}>
          No IPs currently blocked
        </div>
      ) : (
        <div style={{ maxHeight: 200, overflowY: 'auto' }}>
          {blocked.map(b => (
            <div key={b.ip} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 12px', borderRadius: 8, marginBottom: 4,
              background: '#0f172a', border: '1px solid #334155',
            }}>
              <div>
                <span style={{ color: '#f87171', fontWeight: 600, fontFamily: 'monospace', fontSize: 13 }}>
                  {b.ip}
                </span>
                <span style={{
                  marginLeft: 8, padding: '2px 6px', borderRadius: 4,
                  background: b.attack_class === 'DDoS' ? '#7f1d1d' : b.attack_class === 'DoS' ? '#7c2d12' :
                    b.attack_class === 'BruteForce' ? '#78350f' : '#4c1d95',
                  color: '#fbbf24', fontSize: 10, fontWeight: 500,
                }}>
                  {b.attack_class}
                </span>
                <span style={{ marginLeft: 8, color: '#64748b', fontSize: 11 }}>
                  {new Date(b.blocked_at).toLocaleTimeString()}
                </span>
              </div>
              <button
                onClick={() => handleUnblock(b.ip)}
                style={{
                  padding: '2px 8px', borderRadius: 4, border: '1px solid #475569',
                  background: 'transparent', color: '#94a3b8', fontSize: 11,
                  cursor: 'pointer',
                }}
              >
                Unblock
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
