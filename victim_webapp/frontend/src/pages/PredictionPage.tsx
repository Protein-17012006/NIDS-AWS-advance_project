import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { DatasetInfo, ModelInfo, PredictResponse } from '../types';
import ConfusionMatrix from '../components/charts/ConfusionMatrix';
import MetricsBarChart from '../components/charts/MetricsBarChart';
import ClassDistribution from '../components/charts/ClassDistribution';

const PredictionPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    Promise.all([api.getDatasets(), api.getModels()]).then(([ds, ms]) => {
      setDatasets(ds);
      setModels(ms);
      if (ds.length) setSelectedDataset(ds[0].key);
      if (ms.length) setSelectedModel(ms[0].key);
    }).catch(e => setError(e.message));
  }, []);

  useEffect(() => {
    if (!autoRefresh || !selectedDataset || !selectedModel) return;
    const interval = setInterval(() => runPrediction(), 10000);
    return () => clearInterval(interval);
  }, [autoRefresh, selectedDataset, selectedModel]);

  const runPrediction = async () => {
    if (!selectedDataset || !selectedModel) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.predict(selectedDataset, selectedModel);
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const selectedDs = datasets.find(d => d.key === selectedDataset);

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px' }}>
      {/* Controls */}
      <div style={{
        background: '#1e293b', borderRadius: 12, padding: '24px',
        border: '1px solid #334155', marginBottom: 24,
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto auto', gap: 16, alignItems: 'end' }}>
          {/* Dataset Selector */}
          <div>
            <label style={{ color: '#94a3b8', fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 6 }}>
              Dataset
            </label>
            <select
              value={selectedDataset}
              onChange={e => { setSelectedDataset(e.target.value); setResult(null); }}
              style={{
                width: '100%', padding: '10px 14px', borderRadius: 8,
                background: '#0f172a', color: '#e2e8f0', border: '1px solid #475569',
                fontSize: 14, cursor: 'pointer', outline: 'none',
              }}
            >
              {datasets.map(ds => (
                <option key={ds.key} value={ds.key}>
                  {ds.display} ({ds.total_samples.toLocaleString()} samples, {ds.num_features} features)
                </option>
              ))}
            </select>
          </div>

          {/* Model Selector */}
          <div>
            <label style={{ color: '#94a3b8', fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 6 }}>
              Model
            </label>
            <select
              value={selectedModel}
              onChange={e => { setSelectedModel(e.target.value); setResult(null); }}
              style={{
                width: '100%', padding: '10px 14px', borderRadius: 8,
                background: '#0f172a', color: '#e2e8f0', border: '1px solid #475569',
                fontSize: 14, cursor: 'pointer', outline: 'none',
              }}
            >
              {models.map(m => (
                <option key={m.key} value={m.key}>{m.display}</option>
              ))}
            </select>
          </div>

          {/* Run button */}
          <button
            onClick={runPrediction}
            disabled={loading}
            style={{
              padding: '10px 28px', borderRadius: 8, border: 'none',
              background: loading ? '#475569' : '#2563eb',
              color: '#fff', fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer',
              transition: 'all 0.2s',
              height: 42,
            }}
          >
            {loading ? 'Running...' : 'Run Prediction'}
          </button>

          {/* Auto-refresh */}
          <label style={{
            display: 'flex', alignItems: 'center', gap: 8, color: '#94a3b8',
            fontSize: 13, cursor: 'pointer', height: 42,
          }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              style={{ accentColor: '#2563eb' }}
            />
            Auto-refresh
          </label>
        </div>

        {/* Dataset info */}
        {selectedDs && (
          <div style={{ display: 'flex', gap: 24, marginTop: 16, flexWrap: 'wrap' }}>
            {Object.entries(selectedDs.class_distribution).map(([cls, count]) => (
              <div key={cls} style={{
                padding: '6px 14px', borderRadius: 6, fontSize: 12,
                background: '#0f172a', border: '1px solid #334155',
              }}>
                <span style={{ color: '#94a3b8' }}>{cls}:</span>{' '}
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div style={{
          background: '#7f1d1d', borderRadius: 8, padding: '12px 16px',
          color: '#fca5a5', marginBottom: 16, border: '1px solid #991b1b',
        }}>
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !result && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{
              background: '#1e293b', borderRadius: 12, height: 420,
              border: '1px solid #334155', animation: 'pulse 1.5s infinite',
            }} />
          ))}
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Summary cards */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24,
          }}>
            <SummaryCard label="Accuracy" value={`${(result.accuracy * 100).toFixed(2)}%`} color="#10b981" />
            <SummaryCard label="Macro F1" value={`${(result.macro_avg.f1_score * 100).toFixed(2)}%`} color="#3b82f6" />
            <SummaryCard label="Weighted F1" value={`${(result.weighted_avg.f1_score * 100).toFixed(2)}%`} color="#f59e0b" />
            <SummaryCard label="Samples" value={result.sample_count.toLocaleString()} color="#8b5cf6" />
          </div>

          {/* Charts grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
            <ConfusionMatrix data={result} />
            <MetricsBarChart data={result} />
          </div>
          <ClassDistribution data={result} />
        </>
      )}
    </div>
  );
};

const SummaryCard: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div style={{
    background: '#1e293b', borderRadius: 12, padding: '20px',
    border: '1px solid #334155', textAlign: 'center',
  }}>
    <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 4 }}>{label}</div>
    <div style={{ color, fontSize: 28, fontWeight: 700 }}>{value}</div>
  </div>
);

export default PredictionPage;
