import React, { useState, useCallback, useRef } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { IncidentPage } from './pages/IncidentPage';
import { ChaosSimulator } from './components/ChaosSimulator';
import { MetricsPanel } from './components/MetricsPanel';
import { useWebSocket } from './hooks/useWebSocket';
import type { WsMessage } from './types';
import './index.css';

export default function App() {
  const [wsMessages, setWsMessages] = useState<WsMessage[]>([]);
  const [activeIncidents, setActiveIncidents] = useState(0);

  const handleMessage = useCallback((msg: WsMessage) => {
    setWsMessages(prev => [...prev.slice(-99), msg]);
    if (msg.event === 'initial_state') {
      const data = msg.data as { total_active?: number };
      setActiveIncidents(data?.total_active ?? 0);
    } else if (msg.event === 'incident_created') {
      setActiveIncidents(prev => prev + 1);
    } else if (msg.event === 'status_changed') {
      if ((msg as { to_status?: string }).to_status === 'CLOSED') {
        setActiveIncidents(prev => Math.max(0, prev - 1));
      }
    }
  }, []);

  const { status: wsStatus } = useWebSocket(handleMessage);

  return (
    <BrowserRouter>
      <Layout wsStatus={wsStatus} activeIncidents={activeIncidents}>
        <Routes>
          <Route path="/" element={<Dashboard wsMessages={wsMessages} />} />
          <Route path="/incidents" element={<Dashboard wsMessages={wsMessages} />} />
          <Route path="/incidents/:id" element={<IncidentPage />} />
          <Route path="/metrics" element={
            <div style={{ maxWidth: '900px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 800, marginBottom: '20px' }}>System Metrics</h2>
              <MetricsPanel summary={null} signalsPerSec={0} />
            </div>
          } />
          <Route path="/chaos" element={<ChaosSimulator />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
