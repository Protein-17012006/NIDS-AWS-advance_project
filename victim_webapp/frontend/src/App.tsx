import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import PredictionPage from './pages/PredictionPage';
import ComparisonPage from './pages/ComparisonPage';
import AboutPage from './pages/AboutPage';
import LoginPage from './pages/LoginPage';

const navLinkStyle = (isActive: boolean): React.CSSProperties => ({
  color: isActive ? '#3b82f6' : '#94a3b8',
  textDecoration: 'none',
  padding: '8px 16px',
  borderRadius: 8,
  fontSize: 14,
  fontWeight: isActive ? 600 : 400,
  background: isActive ? 'rgba(59,130,246,0.1)' : 'transparent',
  transition: 'all 0.2s',
});

const App: React.FC = () => {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState('');

  const handleLogin = (token: string, user: string) => {
    setLoggedIn(true);
    setUsername(user);
  };

  const handleLogout = () => {
    setLoggedIn(false);
    setUsername('');
  };

  if (!loggedIn) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <BrowserRouter>
      <div style={{
        minHeight: '100vh',
        background: '#0f172a',
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      }}>
        {/* Navbar */}
        <nav style={{
          background: '#1e293b',
          borderBottom: '1px solid #334155',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          height: 60,
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, marginRight: 40,
          }}>
            <span style={{ fontSize: 24 }}>&#128737;&#65039;</span>
            <span style={{ color: '#e2e8f0', fontWeight: 700, fontSize: 18 }}>NIDS ML Platform</span>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <NavLink to="/" end style={({ isActive }) => navLinkStyle(isActive)}>
              Prediction
            </NavLink>
            <NavLink to="/compare" style={({ isActive }) => navLinkStyle(isActive)}>
              Comparison
            </NavLink>
            <NavLink to="/about" style={({ isActive }) => navLinkStyle(isActive)}>
              About
            </NavLink>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{
              color: '#64748b', fontSize: 12, padding: '4px 12px',
              background: '#0f172a', borderRadius: 6, border: '1px solid #334155',
            }}>
              5 Models &times; 3 Datasets
            </span>
            <span style={{ color: '#94a3b8', fontSize: 13 }}>
              {username}
            </span>
            <button
              onClick={handleLogout}
              style={{
                padding: '6px 14px', borderRadius: 6, background: 'transparent',
                color: '#94a3b8', border: '1px solid #475569', fontSize: 12,
                cursor: 'pointer', transition: 'all 0.2s',
              }}
            >
              Logout
            </button>
          </div>
        </nav>

        {/* Page content */}
        <Routes>
          <Route path="/" element={<PredictionPage />} />
          <Route path="/compare" element={<ComparisonPage />} />
          <Route path="/about" element={<AboutPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
};

export default App;
