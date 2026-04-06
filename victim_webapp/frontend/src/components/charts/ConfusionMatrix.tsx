import React from 'react';
import Plot from 'react-plotly.js';
import { PredictResponse, CLASS_COLORS } from '../../types';

interface Props {
  data: PredictResponse;
}

const ConfusionMatrix: React.FC<Props> = ({ data }) => {
  const { confusion_matrix_pct, class_names } = data;

  const annotations: Plotly.Annotations[] = [];
  for (let i = 0; i < class_names.length; i++) {
    for (let j = 0; j < class_names.length; j++) {
      annotations.push({
        x: class_names[j],
        y: class_names[i],
        text: `${confusion_matrix_pct[i][j].toFixed(1)}%`,
        font: { color: confusion_matrix_pct[i][j] > 50 ? '#fff' : '#1e293b', size: 13 },
        showarrow: false,
        xref: 'x',
        yref: 'y',
      } as any);
    }
  }

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: '16px', border: '1px solid #334155' }}>
      <h3 style={{ color: '#e2e8f0', margin: '0 0 8px', fontSize: 16, fontWeight: 600 }}>
        Confusion Matrix (Plotly.js)
      </h3>
      <Plot
        data={[{
          z: confusion_matrix_pct,
          x: class_names,
          y: class_names,
          type: 'heatmap',
          colorscale: [
            [0, '#0f172a'],
            [0.25, '#1e3a5f'],
            [0.5, '#2563eb'],
            [0.75, '#7c3aed'],
            [1, '#ef4444'],
          ],
          showscale: true,
          colorbar: {
            title: { text: '%', font: { color: '#94a3b8' } },
            tickfont: { color: '#94a3b8' },
          },
          hoverongaps: false,
          hovertemplate: 'True: %{y}<br>Pred: %{x}<br>%{z:.1f}%<extra></extra>',
        }]}
        layout={{
          annotations,
          xaxis: {
            title: { text: 'Predicted', font: { color: '#94a3b8' } },
            tickfont: { color: '#cbd5e1', size: 11 },
            side: 'bottom',
          },
          yaxis: {
            title: { text: 'Actual', font: { color: '#94a3b8' } },
            tickfont: { color: '#cbd5e1', size: 11 },
            autorange: 'reversed',
          },
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          margin: { l: 100, r: 40, t: 10, b: 80 },
          height: 420,
          font: { family: 'Inter, sans-serif' },
        }}
        config={{ responsive: true, displayModeBar: true, displaylogo: false }}
        style={{ width: '100%' }}
      />
    </div>
  );
};

export default ConfusionMatrix;
