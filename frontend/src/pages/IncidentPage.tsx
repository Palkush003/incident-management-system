import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock, Signal as SignalIcon, User, CheckCircle, AlertCircle } from 'lucide-react';
import { getWorkItem, getWorkItemSignals, getWorkItemTimeline, transitionWorkItem, getRCA } from '../api/client';
import { SeverityBadge, StatusBadge, ComponentTypeBadge } from '../components/SeverityBadge';
import { RCAForm } from '../components/RCAForm';
import type { WorkItem, Signal, StateTransition, RCA } from '../types';
import { formatDistanceToNow, format } from 'date-fns';

const NEXT_STATUS: Record<string, string | null> = {
  OPEN: 'INVESTIGATING',
  INVESTIGATING: 'RESOLVED',
  RESOLVED: 'CLOSED',
  CLOSED: null,
};

const TRANSITION_LABELS: Record<string, string> = {
  INVESTIGATING: '▶ Start Investigation',
  RESOLVED: '✓ Mark as Resolved',
  CLOSED: '🔒 Close Incident',
};

export const IncidentPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [incident, setIncident] = useState<WorkItem | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [timeline, setTimeline] = useState<StateTransition[]>([]);
  const [rca, setRca] = useState<RCA | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const [activeTab, setActiveTab] = useState<'signals' | 'rca' | 'timeline'>('signals');
  const [assignedTo, setAssignedTo] = useState('');
  const [transitionError, setTransitionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    try {
      const [wi, sigs, tl] = await Promise.all([
        getWorkItem(id),
        getWorkItemSignals(id, 50),
        getWorkItemTimeline(id),
      ]);
      setIncident(wi);
      setSignals(sigs.signals);
      setTimeline(tl);

      if (wi.rca_id) {
        const rcaData = await getRCA(id);
        setRca(rcaData);
      }
    } catch { /* ignore */ } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handleTransition = async () => {
    if (!incident || !id) return;
    const next = NEXT_STATUS[incident.status];
    if (!next) return;

    if (next === 'CLOSED' && !incident.rca_id) {
      setTransitionError('Cannot close — an RCA must be submitted first. Switch to the RCA tab.');
      return;
    }

    setTransitioning(true);
    setTransitionError(null);
    try {
      const updated = await transitionWorkItem(id, next, assignedTo || undefined);
      setIncident(updated);
      await load();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Transition failed';
      setTransitionError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setTransitioning(false);
    }
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
        <div className="spinner" style={{ width: 32, height: 32 }} />
      </div>
    );
  }

  if (!incident) return (
    <div className="empty-state">
      <AlertCircle size={40} />
      <h3>Incident Not Found</h3>
      <p>The incident may have been deleted or the ID is incorrect.</p>
      <button className="btn btn-ghost" onClick={() => navigate('/')}>← Back to Dashboard</button>
    </div>
  );

  const next = NEXT_STATUS[incident.status];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1000px' }}>
      {/* Back navigation */}
      <button className="btn btn-ghost" onClick={() => navigate('/')} style={{ alignSelf: 'flex-start' }}>
        <ArrowLeft size={14} /> Back to Dashboard
      </button>

      {/* Incident header */}
      <div className="glass-card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '20px', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', flexWrap: 'wrap' }}>
              <SeverityBadge severity={incident.severity} />
              <StatusBadge status={incident.status} />
              <ComponentTypeBadge type={incident.component_type} />
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '8px' }}>{incident.title}</h1>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', fontSize: '12px', color: 'var(--text-muted)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Clock size={11} /> Created {formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <SignalIcon size={11} /> {incident.signal_count} signals received
              </span>
              {incident.assigned_to && (
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <User size={11} /> {incident.assigned_to}
                </span>
              )}
              {incident.mttr_minutes && (
                <span style={{ color: 'var(--accent-green)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <CheckCircle size={11} /> MTTR: {Math.round(incident.mttr_minutes)}m
                </span>
              )}
            </div>
          </div>

          {/* Transition action */}
          {next && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-end' }}>
              {incident.status === 'OPEN' && (
                <input
                  type="text"
                  className="form-input"
                  placeholder="Assign to (optional)"
                  value={assignedTo}
                  onChange={e => setAssignedTo(e.target.value)}
                  style={{ width: '200px', padding: '8px 12px', fontSize: '13px' }}
                />
              )}
              <button
                className={`btn ${next === 'CLOSED' ? 'btn-success' : 'btn-primary'}`}
                onClick={handleTransition}
                disabled={transitioning || incident.status === 'CLOSED'}
              >
                {transitioning ? <><div className="spinner" style={{ width: 13, height: 13 }} /> Processing...</> : TRANSITION_LABELS[next]}
              </button>
              {transitionError && (
                <div style={{ fontSize: '12px', color: 'var(--p0-color)', maxWidth: '260px', textAlign: 'right' }}>
                  ⚠ {transitionError}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0' }}>
        {(['signals', 'rca', 'timeline'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              background: 'none',
              border: 'none',
              padding: '10px 20px',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 600,
              color: activeTab === tab ? 'var(--accent-blue)' : 'var(--text-muted)',
              borderBottom: activeTab === tab ? '2px solid var(--accent-blue)' : '2px solid transparent',
              marginBottom: '-1px',
              transition: 'color 0.15s ease',
              textTransform: 'capitalize',
            }}
          >
            {tab === 'rca' ? 'Root Cause Analysis' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            {tab === 'rca' && incident.rca_id && (
              <span style={{ marginLeft: '6px', color: 'var(--accent-green)' }}>✓</span>
            )}
            {tab === 'rca' && !incident.rca_id && incident.status !== 'CLOSED' && (
              <span style={{ marginLeft: '6px', color: 'var(--p0-color)', fontSize: '10px' }}>REQUIRED</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="animate-in">
        {activeTab === 'signals' && (
          <div className="glass-card">
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', fontSize: '13px', color: 'var(--text-muted)' }}>
              Showing latest {signals.length} of {incident.signal_count} raw signals (stored in MongoDB)
            </div>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Component</th>
                    <th>Severity</th>
                    <th>Message</th>
                    <th>Error Code</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.map(sig => (
                    <tr key={sig.id}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', whiteSpace: 'nowrap' }}>
                        {format(new Date(sig.ingested_at || sig.timestamp), 'HH:mm:ss.SSS')}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>{sig.component_id}</td>
                      <td><SeverityBadge severity={sig.severity} showPulse={false} /></td>
                      <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sig.message}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-code)' }}>{sig.error_code ?? '—'}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>{sig.source_host ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'rca' && (
          <div className="glass-card" style={{ padding: '24px' }}>
            {rca ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-green)' }}>
                  <CheckCircle size={18} />
                  <span style={{ fontWeight: 700 }}>RCA Submitted by {rca.submitted_by}</span>
                </div>
                {[
                  ['Root Cause Category', rca.root_cause_category],
                  ['Root Cause Description', rca.root_cause_description],
                  ['Fix Applied', rca.fix_applied],
                  ['Prevention Steps', rca.prevention_steps],
                  ['MTTR', `${Math.round(rca.mttr_minutes)} minutes`],
                  ['Affected Services', rca.affected_services.join(', ') || 'None specified'],
                ].map(([label, value]) => (
                  <div key={label}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>{label}</div>
                    <div style={{ fontSize: '14px', color: 'var(--text-primary)', lineHeight: 1.6 }}>{value}</div>
                  </div>
                ))}
              </div>
            ) : (
              <RCAForm workItemId={incident.id} onSuccess={async (r) => { setRca(r); await load(); }} />
            )}
          </div>
        )}

        {activeTab === 'timeline' && (
          <div className="glass-card" style={{ padding: '24px' }}>
            <div className="timeline">
              {/* Creation event */}
              <div className="timeline-item">
                <div className="timeline-connector">
                  <div className="timeline-dot" style={{ borderColor: 'var(--p0-color)', background: 'var(--p0-color)' }} />
                  <div className="timeline-line" />
                </div>
                <div className="timeline-content">
                  <div style={{ fontSize: '13px', fontWeight: 600 }}>Incident Created</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {format(new Date(incident.created_at), 'MMM d, yyyy HH:mm:ss')}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    First signal received from {incident.component_id}
                  </div>
                </div>
              </div>

              {timeline.map((t, i) => (
                <div key={i} className="timeline-item">
                  <div className="timeline-connector">
                    <div className="timeline-dot" style={{
                      borderColor: {
                        OPEN: 'var(--p0-color)', INVESTIGATING: 'var(--p1-color)',
                        RESOLVED: 'var(--accent-green)', CLOSED: 'var(--text-muted)',
                      }[t.to_status] ?? 'var(--accent-blue)',
                      background: 'transparent',
                    }} />
                    {i < timeline.length - 1 && <div className="timeline-line" />}
                  </div>
                  <div className="timeline-content">
                    <div style={{ fontSize: '13px', fontWeight: 600 }}>
                      {t.from_status} → <span style={{ color: 'var(--accent-blue)' }}>{t.to_status}</span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {format(new Date(t.transitioned_at), 'MMM d, yyyy HH:mm:ss')}
                      {t.transitioned_by && ` · by ${t.transitioned_by}`}
                    </div>
                    {t.notes && <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', fontStyle: 'italic' }}>{t.notes}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
