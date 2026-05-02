import React, { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { Activity, TrendingUp, Clock, Shield } from 'lucide-react';
import { getDashboardMetrics, getMttrStats, getDashboardSummary } from '../api/client';
import type { DashboardSummary } from '../types';

interface MetricsPanelProps {
  summary: DashboardSummary | null;
  signalsPerSec: number;
}

const SEVERITY_COLORS: Record<string, string> = {
  P0: '#ef4444', P1: '#f97316', P2: '#eab308', P3: '#06b6d4',
};

export const MetricsPanel: React.FC<MetricsPanelProps> = ({ summary, signalsPerSec }) => {
  const [throughputData, setThroughputData] = useState<{ time: string; count: number }[]>([]);
  const [mttrStats, setMttrStats] = useState<unknown[]>([]);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const [metrics, mttr] = await Promise.all([getDashboardMetrics(60), getMttrStats()]);
        const series = metrics.series
          .slice(-30)
          .map(p => ({
            time: new Date(p.timestamp * 1000).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            count: p.count,
          }));
        setThroughputData(series);
        setMttrStats(mttr);
      } catch { /* ignore */ }
    };
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  const severityData = summary
    ? Object.entries(summary.by_severity).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
      {/* Top metrics row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <div className="glass-card metric-card">
          <div className="metric-label">Signals / sec</div>
          <div className="metric-value" style={{ fontSize: '28px' }}>
            {signalsPerSec.toFixed(1)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Activity size={11} color="var(--accent-green)" />
            <span style={{ fontSize: '11px', color: 'var(--accent-green)' }}>Live</span>
          </div>
        </div>
        <div className="glass-card metric-card">
          <div className="metric-label">Avg MTTR</div>
          <div className="metric-value" style={{ fontSize: '28px' }}>
            {summary ? `${Math.round(summary.avg_mttr_minutes)}m` : '—'}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Clock size={11} color="var(--accent-blue)" />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>mean time to repair</span>
          </div>
        </div>
        <div className="glass-card metric-card">
          <div className="metric-label">Active Incidents</div>
          <div className="metric-value" style={{ fontSize: '28px', background: 'linear-gradient(135deg, var(--p0-color), var(--p1-color))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
            {summary?.total_active ?? 0}
          </div>
        </div>
        <div className="glass-card metric-card">
          <div className="metric-label">Closed (Total)</div>
          <div className="metric-value" style={{ fontSize: '28px' }}>
            {summary?.by_status?.CLOSED ?? 0}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Shield size={11} color="var(--accent-green)" />
            <span style={{ fontSize: '11px', color: 'var(--accent-green)' }}>resolved</span>
          </div>
        </div>
      </div>

      {/* Throughput chart */}
      <div className="glass-card" style={{ padding: '16px', flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <TrendingUp size={14} color="var(--accent-blue)" />
          <span style={{ fontSize: '13px', fontWeight: 600 }}>Signal Throughput (last 30s)</span>
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={throughputData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="throughputGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#4a6080' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10, fill: '#4a6080' }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', borderRadius: '8px', fontSize: '12px' }}
              labelStyle={{ color: 'var(--text-secondary)' }}
            />
            <Area type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2} fill="url(#throughputGradient)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Severity distribution */}
      {severityData.length > 0 && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, marginBottom: '12px', display: 'block' }}>By Severity</span>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <PieChart width={200} height={140}>
              <Pie data={severityData} cx={100} cy={70} innerRadius={35} outerRadius={60} paddingAngle={3} dataKey="value">
                {severityData.map((entry, index) => (
                  <Cell key={index} fill={SEVERITY_COLORS[entry.name] ?? '#6b7280'} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', borderRadius: '8px', fontSize: '12px' }} />
              <Legend wrapperStyle={{ fontSize: '11px', color: 'var(--text-secondary)' }} />
            </PieChart>
          </div>
        </div>
      )}
    </div>
  );
};
