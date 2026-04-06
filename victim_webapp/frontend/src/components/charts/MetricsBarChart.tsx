import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { PredictResponse, CLASS_COLORS } from '../../types';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

interface Props {
  data: PredictResponse;
}

const MetricsBarChart: React.FC<Props> = ({ data }) => {
  const { per_class, class_names } = data;

  const labels = class_names;
  const precisions = labels.map(c => per_class[c]?.precision ?? 0);
  const recalls = labels.map(c => per_class[c]?.recall ?? 0);
  const f1s = labels.map(c => per_class[c]?.f1_score ?? 0);

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Precision',
        data: precisions,
        backgroundColor: 'rgba(59, 130, 246, 0.8)',
        borderColor: '#3b82f6',
        borderWidth: 1,
        borderRadius: 4,
      },
      {
        label: 'Recall',
        data: recalls,
        backgroundColor: 'rgba(16, 185, 129, 0.8)',
        borderColor: '#10b981',
        borderWidth: 1,
        borderRadius: 4,
      },
      {
        label: 'F1-Score',
        data: f1s,
        backgroundColor: 'rgba(245, 158, 11, 0.8)',
        borderColor: '#f59e0b',
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: { color: '#cbd5e1', font: { family: 'Inter', size: 12 } },
      },
      tooltip: {
        callbacks: {
          label: (ctx: any) => `${ctx.dataset.label}: ${(ctx.raw * 100).toFixed(1)}%`,
        },
      },
    },
    scales: {
      x: {
        ticks: { color: '#cbd5e1', font: { size: 11 } },
        grid: { color: 'rgba(71, 85, 105, 0.3)' },
      },
      y: {
        min: 0,
        max: 1,
        ticks: {
          color: '#94a3b8',
          callback: (v: any) => `${(v * 100).toFixed(0)}%`,
        },
        grid: { color: 'rgba(71, 85, 105, 0.3)' },
      },
    },
  };

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: '16px', border: '1px solid #334155' }}>
      <h3 style={{ color: '#e2e8f0', margin: '0 0 8px', fontSize: 16, fontWeight: 600 }}>
        Per-Class Metrics (Chart.js)
      </h3>
      <div style={{ height: 380 }}>
        <Bar data={chartData} options={options} />
      </div>
    </div>
  );
};

export default MetricsBarChart;
