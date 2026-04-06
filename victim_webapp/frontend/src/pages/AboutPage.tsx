import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { DatasetInfo, ModelInfo } from '../types';

const AboutPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);

  useEffect(() => {
    Promise.all([api.getDatasets(), api.getModels()]).then(([ds, ms]) => {
      setDatasets(ds);
      setModels(ms);
    });
  }, []);

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '24px' }}>
      {/* Hero */}
      <div style={{
        background: 'linear-gradient(135deg, #1e3a5f 0%, #1e293b 100%)',
        borderRadius: 16, padding: '48px 40px', border: '1px solid #334155',
        marginBottom: 32, textAlign: 'center',
      }}>
        <h1 style={{ color: '#e2e8f0', fontSize: 36, fontWeight: 700, margin: '0 0 12px' }}>
          NIDS ML Prediction Platform
        </h1>
        <p style={{ color: '#94a3b8', fontSize: 18, margin: 0, maxWidth: 700, marginLeft: 'auto', marginRight: 'auto' }}>
          Network Intrusion Detection System — Machine Learning models trained on real-world
          network traffic datasets to classify attacks in real-time.
        </p>
      </div>

      {/* Architecture */}
      <Section title="System Architecture">
        <p style={pStyle}>
          This platform provides a web interface for exploring and evaluating 5 machine learning models
          across 3 benchmark network intrusion detection datasets. The system classifies network traffic
          into 5 categories:
        </p>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 12 }}>
          {['BENIGN', 'BruteForce', 'DDoS', 'DoS', 'Infiltration'].map(cls => (
            <span key={cls} style={{
              padding: '6px 16px', borderRadius: 20, fontSize: 13, fontWeight: 600,
              background: cls === 'BENIGN' ? '#064e3b' : cls === 'DDoS' ? '#7f1d1d' :
                cls === 'DoS' ? '#7c2d12' : cls === 'BruteForce' ? '#78350f' : '#4c1d95',
              color: '#e2e8f0', border: '1px solid rgba(255,255,255,0.1)',
            }}>{cls}</span>
          ))}
        </div>
      </Section>

      {/* Datasets */}
      <Section title="Datasets">
        {datasets.map(ds => (
          <div key={ds.key} style={{
            background: '#0f172a', borderRadius: 10, padding: '16px 20px',
            border: '1px solid #334155', marginBottom: 12,
          }}>
            <h4 style={{ color: '#e2e8f0', margin: '0 0 8px' }}>{ds.display}</h4>
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', color: '#94a3b8', fontSize: 13 }}>
              <span>Samples: <strong style={{ color: '#cbd5e1' }}>{ds.total_samples.toLocaleString()}</strong></span>
              <span>Features: <strong style={{ color: '#cbd5e1' }}>{ds.num_features}</strong></span>
              <span>Classes: <strong style={{ color: '#cbd5e1' }}>{ds.classes.length}</strong></span>
            </div>
          </div>
        ))}
      </Section>

      {/* Models */}
      <Section title="Machine Learning Models">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {models.map(m => (
            <div key={m.key} style={{
              background: '#0f172a', borderRadius: 10, padding: '16px 20px',
              border: '1px solid #334155',
            }}>
              <h4 style={{ color: '#e2e8f0', margin: '0 0 6px' }}>{m.display}</h4>
              <p style={{ color: '#94a3b8', fontSize: 12, margin: 0 }}>
                {m.needs_scaler ? 'Uses StandardScaler' : 'No scaling needed'}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* Pipeline */}
      <Section title="Preprocessing Pipeline">
        <ol style={{ color: '#cbd5e1', lineHeight: 2, paddingLeft: 20 }}>
          <li>Label mapping → 5 unified attack classes</li>
          <li>Drop metadata columns (IPs, ports, timestamps, flow IDs)</li>
          <li>Handle infinity → NaN → median fill</li>
          <li>Variance threshold filtering (threshold = 0.01)</li>
          <li>Z-score outlier removal (|z| &lt; 3)</li>
          <li>Correlation filtering (Pearson r &gt; 0.95)</li>
          <li>Stratified train/test split (80/20)</li>
          <li>StandardScaler (KNN, Logistic Regression, SVM only)</li>
        </ol>
      </Section>

      {/* Tech */}
      <Section title="Technology Stack">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, color: '#cbd5e1' }}>
          <div>
            <h4 style={{ color: '#3b82f6', marginBottom: 8 }}>Backend</h4>
            <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 2 }}>
              <li>FastAPI (Python 3.10)</li>
              <li>scikit-learn</li>
              <li>pandas / numpy</li>
              <li>WebSocket support</li>
            </ul>
          </div>
          <div>
            <h4 style={{ color: '#10b981', marginBottom: 8 }}>Frontend</h4>
            <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 2 }}>
              <li>React 18 + TypeScript</li>
              <li>Plotly.js — Confusion Matrix</li>
              <li>Chart.js — Metrics Bar Charts</li>
              <li>D3.js — Class Distribution</li>
            </ul>
          </div>
        </div>
      </Section>
    </div>
  );
};

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div style={{
    background: '#1e293b', borderRadius: 12, padding: '24px',
    border: '1px solid #334155', marginBottom: 24,
  }}>
    <h3 style={{ color: '#e2e8f0', margin: '0 0 16px', fontSize: 20, fontWeight: 600 }}>{title}</h3>
    {children}
  </div>
);

const pStyle: React.CSSProperties = { color: '#cbd5e1', lineHeight: 1.7, margin: 0 };

export default AboutPage;
