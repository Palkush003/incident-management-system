import React, { useEffect, useState, useCallback } from 'react';
import { LiveFeed } from '../components/LiveFeed';
import { MetricsPanel } from '../components/MetricsPanel';
import { getWorkItems, getDashboardSummary } from '../api/client';
import type { WorkItem, DashboardSummary, WsMessage } from '../types';

interface DashboardProps {
  wsMessages: WsMessage[];
}

export const Dashboard: React.FC<DashboardProps> = ({ wsMessages }) => {
  const [incidents, setIncidents] = useState<WorkItem[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [signalsPerSec, setSignalsPerSec] = useState(0);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [items, sum] = await Promise.all([
        getWorkItems({ status: 'OPEN', limit: 100 }),
        getDashboardSummary(),
      ]);
      setIncidents(items);
      setSummary(sum);
      setSignalsPerSec(sum.signals_per_sec ?? 0);
    } catch { /* ignore */ } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Handle real-time WebSocket events
  useEffect(() => {
    const lastMsg = wsMessages[wsMessages.length - 1];
    if (!lastMsg) return;

    if (lastMsg.event === 'incident_created') {
      const wi = lastMsg.work_item as WorkItem;
      setIncidents(prev => {
        const exists = prev.some(i => i.id === wi.id);
        if (exists) return prev;
        return [wi, ...prev];
      });
    } else if (lastMsg.event === 'status_changed') {
      const { work_item_id, to_status } = lastMsg as unknown as { work_item_id: string; to_status: string };
      setIncidents(prev =>
        to_status === 'CLOSED'
          ? prev.filter(i => i.id !== work_item_id)
          : prev.map(i => i.id === work_item_id ? { ...i, status: to_status as WorkItem['status'] } : i)
      );
    }
  }, [wsMessages]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: '0' }}>
      {/* Page header */}
      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 800, marginBottom: '4px' }}>Operations Dashboard</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Real-time monitoring of all system components and active incidents</p>
      </div>

      {/* Main split layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '16px', flex: 1, minHeight: 0 }}>
        <LiveFeed
          incidents={incidents}
          onRefresh={loadData}
          isLoading={isLoading}
        />
        <MetricsPanel summary={summary} signalsPerSec={signalsPerSec} />
      </div>
    </div>
  );
};
