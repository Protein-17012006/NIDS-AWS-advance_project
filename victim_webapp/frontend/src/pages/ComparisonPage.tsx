import React, { useState, useEffect } from 'react';
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { api } from '../services/api';
import { DatasetInfo, CompareResponse, MODEL_COLORS } from '../types';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const ComparisonPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getDatasets().then(ds => {
      setDatasets(ds);
      if (ds.length) setSelectedDataset(ds[0].key);
    });
  }, []);

  const runCompare = async () => {
    if (!selectedDataset) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.compare(selectedDataset);
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const models = result?.results || [];

  const accuracyData = {
    labels: models.map(r => r.model.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())),
    datasets: [{
      label: 'Accuracy',
      data: models.map(r => r.accuracy),
      backgroundColor: models.map(r => MODEL_COLORS[r.model] || '#64748b'),
      borderRadius: 6,
      borderWidth: 0,
    }],
  };

  const f1Data = {
    labels: models.map(r => r.model.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())),
    datasets: [
      {
        label: 'Macro F1',
        data: models.map(r => r.macro_avg.f1_score),
        backgroundColor: 'rgba(59, 130, 246, 0.8)',
        borderRadius: 6,
      },
      {
        label: 'Weighted F1',
        data: models.map(r => r.weighted_avg.f1_score),
        backgroundColor: 'rgba(16, 185, 129, 0.8)',
        borderRadius: 6,
      },
    ],
  };

  const chartOptions = (title: string) => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: '#cbd5e1', font: { family: 'Inter' } } },
      title: { display: true, text: title, color: '#e2e8f0', font: { size: 16, family: 'Inter' } },
      tooltip: {
        callbacks: { label: (ctx: any) => `${ctx.dataset.label}: ${(ctx.raw * 100).toFixed(2)}%` },
      },
    },
    scales: {
      x: { ticks: { color: '#cbd5e1' }, grid: { color: 'rgba(71,85,105,0.3)' } },
      y: {
        min: 0, max: 1,
        ticks: { color: '#94a3b8', callback: (v: any) => `${(v * 100).toFixed(0)}%` },
        grid: { color: 'rgba(71,85,105,0.3)' },
      },
    },
  });

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px' }}>
      {/* Controls */}
      <div style={{
        background: '#1e293b', borderRadius: 12, padding: '24px',
        border: '1px solid #334155', marginBottom: 24,
        display: 'flex', gap: 16, alignItems: 'end',
      }}>
        <div style={{ flex: 1 }}>
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
              <option key={ds.key} value={ds.key}>{ds.display}</option>
            ))}
          </select>
        </div>
        <button
          onClick={runCompare}
          disabled={loading}
          style={{
            padding: '10px 28px', borderRadius: 8, border: 'none',
            background: loading ? '#475569' : '#7c3aed',
            color: '#fff', fontSize: 14, fontWeight: 600,
            cursor: loading ? 'wait' : 'pointer', height: 42,
          }}
        >
          {loading ? 'Running all 5 models...' : 'Compare All Models'}
        </button>
      </div>

      {error && (
        <div style={{
          background: '#7f1d1d', borderRadius: 8, padding: '12px 16px',
          color: '#fca5a5', marginBottom: 16, border: '1px solid #991b1b',
        }}>{error}</div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 60, color: '#94a3b8' }}>
          <div style={{
            width: 48, height: 48, border: '4px solid #334155', borderTop: '4px solid #7c3aed',
            borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px',
          }} />
          Running all 5 models on {selectedDataset}...
        </div>
      )}

      {/* Results */}
      {result && models.length > 0 && (
        <>
          {/* Summary table */}
          <div style={{
            background: '#1e293b', borderRadius: 12, padding: '20px',
            border: '1px solid #334155', marginBottom: 24, overflowX: 'auto',
          }}>
            <h3 style={{ color: '#e2e8f0', marginBottom: 12 }}>Model Comparison Summary</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #475569' }}>
                  {['Model', 'Accuracy', 'Macro F1', 'Weighted F1', 'Macro Precision', 'Macro Recall'].map(h => (
                    <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: '#94a3b8', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {models.map(r => (
                  <tr key={r.model} style={{ borderBottom: '1px solid #334155' }}>
                    <td style={{ padding: '10px 12px', color: '#e2e8f0', fontWeight: 500 }}>
                      <span style={{
                        display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                        background: MODEL_COLORS[r.model] || '#64748b', marginRight: 8,
                      }} />
                      {r.model.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#10b981', fontWeight: 600 }}>{(r.accuracy * 100).toFixed(2)}%</td>
                    <td style={{ padding: '10px 12px', color: '#3b82f6' }}>{(r.macro_avg.f1_score * 100).toFixed(2)}%</td>
                    <td style={{ padding: '10px 12px', color: '#f59e0b' }}>{(r.weighted_avg.f1_score * 100).toFixed(2)}%</td>
                    <td style={{ padding: '10px 12px', color: '#cbd5e1' }}>{(r.macro_avg.precision * 100).toFixed(2)}%</td>
                    <td style={{ padding: '10px 12px', color: '#cbd5e1' }}>{(r.macro_avg.recall * 100).toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Charts */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <div style={{ background: '#1e293b', borderRadius: 12, padding: 16, border: '1px solid #334155' }}>
              <div style={{ height: 380 }}>
                <Bar data={accuracyData} options={chartOptions('Accuracy Comparison')} />
              </div>
            </div>
            <div style={{ background: '#1e293b', borderRadius: 12, padding: 16, border: '1px solid #334155' }}>
              <div style={{ height: 380 }}>
                <Bar data={f1Data} options={chartOptions('F1-Score Comparison')} />
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ComparisonPage;
