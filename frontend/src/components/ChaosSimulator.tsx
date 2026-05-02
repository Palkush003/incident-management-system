import React, { useState } from 'react';
import { Zap, Play, Square, AlertTriangle, Database, Server, Radio, Wifi } from 'lucide-react';
import { ingestSignalBatch } from '../api/client';

interface Scenario {
  id: string;
  name: string;
  icon: React.ReactNode;
  description: string;
  severity: string;
  signals: object[];
}

const CHAOS_SCENARIOS: Scenario[] = [
  {
    id: 'rdbms_outage',
    name: 'RDBMS Outage',
    icon: <Database size={16} />,
    description: 'Simulates primary database going down — triggers P0 alert cascade',
    severity: 'P0',
    signals: Array.from({ length: 50 }, (_, i) => ({
      component_id: 'POSTGRES_PRIMARY',
      component_type: 'RDBMS',
      severity: 'P0',
      message: `Connection refused to primary DB: attempt ${i + 1}`,
      error_code: 'ERR_CONNECTION_REFUSED',
      source_host: `app-server-${(i % 5) + 1}`,
      metadata: { replica_count: 2, last_backup: '2024-01-01T00:00:00Z' },
    })),
  },
  {
    id: 'cache_degradation',
    name: 'Cache Cluster Failure',
    icon: <Radio size={16} />,
    description: 'Redis cluster memory exhaustion — triggers P2 debouncing test',
    severity: 'P2',
    signals: Array.from({ length: 120 }, (_, i) => ({
      component_id: 'CACHE_CLUSTER_01',
      component_type: 'CACHE',
      severity: 'P2',
      message: `OOM error on cache node: eviction failed attempt ${i + 1}`,
      error_code: 'ERR_OOM',
      source_host: `cache-node-${(i % 3) + 1}`,
      metadata: { memory_used_mb: 3800 + i, max_memory_mb: 4096 },
    })),
  },
  {
    id: 'mcp_cascade',
    name: 'MCP + API Cascade',
    icon: <Server size={16} />,
    description: 'MCP host failure triggering cascading API failures — full P0/P1 storm',
    severity: 'P0',
    signals: [
      ...Array.from({ length: 30 }, (_, i) => ({
        component_id: 'MCP_HOST_PRIMARY',
        component_type: 'MCP_HOST',
        severity: 'P0',
        message: `MCP host unreachable: timeout ${i + 1}`,
        error_code: 'ERR_TIMEOUT',
        source_host: 'orchestrator-01',
        metadata: {},
      })),
      ...Array.from({ length: 40 }, (_, i) => ({
        component_id: 'API_GATEWAY_01',
        component_type: 'API',
        severity: 'P1',
        message: `Gateway 503: upstream MCP unavailable, request ${i + 1}`,
        error_code: 'HTTP_503',
        source_host: `lb-node-${(i % 2) + 1}`,
        metadata: {},
      })),
    ],
  },
  {
    id: 'queue_saturation',
    name: 'Queue Saturation',
    icon: <Wifi size={16} />,
    description: 'Async queue depth exceeding threshold — P1 alert',
    severity: 'P1',
    signals: Array.from({ length: 80 }, (_, i) => ({
      component_id: 'KAFKA_CLUSTER_MAIN',
      component_type: 'ASYNC_QUEUE',
      severity: 'P1',
      message: `Consumer lag critical: ${10000 + i * 500} messages behind`,
      error_code: 'ERR_CONSUMER_LAG',
      source_host: `kafka-broker-${(i % 3) + 1}`,
      metadata: { lag: 10000 + i * 500, partition: i % 6 },
    })),
  },
];

export const ChaosSimulator: React.FC = () => {
  const [running, setRunning] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, string>>({});
  const [burstRate, setBurstRate] = useState(10);

  const runScenario = async (scenario: Scenario) => {
    setRunning(scenario.id);
    setResults(r => ({ ...r, [scenario.id]: 'running' }));

    try {
      const batchSize = 50;
      const signals = scenario.signals;

      for (let i = 0; i < signals.length; i += batchSize) {
        const batch = signals.slice(i, i + batchSize);
        await ingestSignalBatch(batch);
        await new Promise(resolve => setTimeout(resolve, 1000 / burstRate * batchSize));
      }

      setResults(r => ({ ...r, [scenario.id]: `✓ Sent ${signals.length} signals` }));
    } catch (err) {
      setResults(r => ({ ...r, [scenario.id]: '✗ Failed — is backend running?' }));
    } finally {
      setRunning(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <Zap size={20} color="var(--p1-color)" />
          <h2 style={{ fontSize: '20px', fontWeight: 700 }}>Chaos Monkey Simulator</h2>
          <span style={{ background: 'var(--p1-bg)', color: 'var(--p1-color)', borderRadius: '10px', padding: '2px 10px', fontSize: '11px', fontWeight: 700 }}>BONUS FEATURE</span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: 1.6 }}>
          Simulate real-world failure scenarios to test the system's signal ingestion, debouncing, alerting, and dashboard — all in real-time.
        </p>
      </div>

      {/* Burst rate control */}
      <div className="glass-card" style={{ padding: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600 }}>Signal Burst Rate</span>
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)', fontWeight: 700 }}>{burstRate} signals/batch</span>
        </div>
        <input
          type="range"
          min={1}
          max={100}
          value={burstRate}
          onChange={e => setBurstRate(Number(e.target.value))}
          style={{ width: '100%', accentColor: 'var(--accent-blue)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
          <span>Slow (1/batch)</span>
          <span>Fast (100/batch)</span>
        </div>
      </div>

      {/* Scenario cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        {CHAOS_SCENARIOS.map(scenario => {
          const isRunning = running === scenario.id;
          const result = results[scenario.id];

          return (
            <div key={scenario.id} className="glass-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: `var(--${scenario.severity.toLowerCase()}-color)` }}>{scenario.icon}</span>
                  <span style={{ fontSize: '14px', fontWeight: 700 }}>{scenario.name}</span>
                </div>
                <span className={`badge badge-${scenario.severity.toLowerCase()}`}>{scenario.severity}</span>
              </div>

              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{scenario.description}</p>

              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                📡 {scenario.signals.length} signals → {[...new Set(scenario.signals.map((s: unknown) => (s as { component_id: string }).component_id))].length} components
              </div>

              {result && (
                <div style={{
                  fontSize: '12px',
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-sm)',
                  background: result.startsWith('✓') ? 'rgba(16, 185, 129, 0.1)' : result === 'running' ? 'rgba(234, 179, 8, 0.1)' : 'var(--p0-bg)',
                  color: result.startsWith('✓') ? 'var(--accent-green)' : result === 'running' ? 'var(--p2-color)' : 'var(--p0-color)',
                  fontFamily: 'var(--font-mono)',
                }}>
                  {result === 'running' ? '⏳ Sending signals...' : result}
                </div>
              )}

              <button
                className={`btn ${isRunning ? 'btn-ghost' : 'btn-primary'}`}
                onClick={() => runScenario(scenario)}
                disabled={running !== null}
              >
                {isRunning ? (
                  <><div className="spinner" style={{ width: 13, height: 13 }} /> Running...</>
                ) : (
                  <><Play size={13} /> Launch Scenario</>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* Warning */}
      <div style={{ background: 'rgba(234, 179, 8, 0.08)', border: '1px solid rgba(234, 179, 8, 0.2)', borderRadius: 'var(--radius-md)', padding: '14px 18px', display: 'flex', gap: '10px' }}>
        <AlertTriangle size={16} color="var(--p2-color)" style={{ flexShrink: 0, marginTop: '1px' }} />
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          <strong style={{ color: 'var(--p2-color)' }}>Note:</strong> Chaos scenarios send real signals to the backend. Each scenario will create new Work Items visible in the Dashboard. The debouncing engine will group multiple signals from the same component into a single Work Item.
        </div>
      </div>
    </div>
  );
};
