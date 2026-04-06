import React, { useEffect, useState, useRef } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { LivePredictionEvent, CLASS_COLORS } from '../types';

const CLASS_NAMES = ['Benign', 'BruteForce', 'DDoS', 'DoS', 'Infiltration'];
const MAX_POINTS = 60; // 5 min at 5s intervals

interface DataPoint {
  time: string;
  Benign: number;
  BruteForce: number;
  DDoS: number;
  DoS: number;
  Infiltration: number;
}

interface Props {
  drainEvents: () => LivePredictionEvent[];
}

export default function LiveTrafficChart({ drainEvents }: Props) {
  const [data, setData] = useState<DataPoint[]>([]);

  // Flush bucket every 5 seconds — drain ALL queued events at once
  useEffect(() => {
    const interval = setInterval(() => {
      const events = drainEvents();
      const counts: Record<string, number> = {
        Benign: 0, BruteForce: 0, DDoS: 0, DoS: 0, Infiltration: 0,
      };
      for (const evt of events) {
        if (evt.type === 'prediction' && evt.data?.predicted_class) {
          const cls = evt.data.predicted_class;
          if (cls in counts) counts[cls]++;
        }
      }
      const now = new Date();
      const time = `${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
      setData((prev) => [...prev, { time, ...counts } as DataPoint].slice(-MAX_POINTS));
    }, 5000);
    return () => clearInterval(interval);
  }, [drainEvents]);

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h3 style={{ color: '#e2e8f0', margin: '0 0 12px' }}>Live Traffic (predictions / 5s)</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
          <YAxis stroke="#94a3b8" fontSize={12} />
          <Tooltip contentStyle={{ background: '#0f172a', border: 'none', color: '#e2e8f0' }} />
          <Legend />
          {CLASS_NAMES.map((cls) => (
            <Line
              key={cls}
              type="monotone"
              dataKey={cls}
              stroke={CLASS_COLORS[cls]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
