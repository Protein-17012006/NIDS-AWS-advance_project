import React, { useState } from 'react';

interface LoginPageProps {
  onLogin: (token: string, username: string) => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      onLogin(data.token, data.username);
    } catch (e: any) {
      setError(e.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0f172a',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    }}>
      <div style={{
        background: '#1e293b',
        borderRadius: 16,
        padding: '48px 40px',
        border: '1px solid #334155',
        width: 420,
        boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
      }}>
        {/* Logo / Header */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <span style={{ fontSize: 48 }}>&#128737;&#65039;</span>
          <h1 style={{
            color: '#e2e8f0', fontSize: 24, fontWeight: 700,
            margin: '12px 0 4px',
          }}>
            NIDS ML Platform
          </h1>
          <p style={{ color: '#64748b', fontSize: 14, margin: 0 }}>
            Network Intrusion Detection System
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 20 }}>
            <label style={{
              color: '#94a3b8', fontSize: 13, fontWeight: 500,
              display: 'block', marginBottom: 6,
            }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="Enter your username"
              autoComplete="username"
              autoFocus
              style={{
                width: '100%',
                padding: '12px 14px',
                borderRadius: 8,
                background: '#0f172a',
                color: '#e2e8f0',
                border: '1px solid #475569',
                fontSize: 14,
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{
              color: '#94a3b8', fontSize: 13, fontWeight: 500,
              display: 'block', marginBottom: 6,
            }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
              style={{
                width: '100%',
                padding: '12px 14px',
                borderRadius: 8,
                background: '#0f172a',
                color: '#e2e8f0',
                border: '1px solid #475569',
                fontSize: 14,
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {error && (
            <div style={{
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 8,
              padding: '10px 14px',
              marginBottom: 20,
              color: '#f87171',
              fontSize: 13,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username || !password}
            style={{
              width: '100%',
              padding: '12px 0',
              borderRadius: 8,
              background: loading ? '#1e40af' : '#3b82f6',
              color: '#fff',
              border: 'none',
              fontSize: 15,
              fontWeight: 600,
              cursor: loading ? 'wait' : 'pointer',
              opacity: (!username || !password) ? 0.5 : 1,
              transition: 'all 0.2s',
            }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        {/* Info */}
        <div style={{
          marginTop: 24,
          padding: '12px 14px',
          background: 'rgba(59,130,246,0.08)',
          borderRadius: 8,
          border: '1px solid rgba(59,130,246,0.15)',
        }}>
          <p style={{ color: '#64748b', fontSize: 12, margin: 0, lineHeight: 1.5 }}>
            <strong style={{ color: '#94a3b8' }}>5 ML Models</strong> &times;{' '}
            <strong style={{ color: '#94a3b8' }}>3 Datasets</strong> — Real-time network
            intrusion detection with transfer learning
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
