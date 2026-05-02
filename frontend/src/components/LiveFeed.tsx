import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Clock, Signal, ChevronRight, RefreshCw } from 'lucide-react';
import { SeverityBadge, StatusBadge, ComponentTypeBadge } from './SeverityBadge';
import type { WorkItem, WsMessage } from '../types';
import { getWorkItems } from '../api/client';
import { formatDistanceToNow } from 'date-fns';

interface LiveFeedProps {
  incidents: WorkItem[];
  onRefresh: () => void;
  isLoading: boolean;
}

export const LiveFeed: React.FC<LiveFeedProps> = ({ incidents, onRefresh, isLoading }) => {
  const navigate = useNavigate();

  const severityOrder = { P0: 0, P1: 1, P2: 2, P3: 3 };
  const sorted = [...incidents].sort((a, b) => {
    const sev = severityOrder[a.severity] - severityOrder[b.severity];
    if (sev !== 0) return sev;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  return (
    <div className="glass-card" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <AlertTriangle size={16} color="var(--p0-color)" />
          <span style={{ fontWeight: 600, fontSize: '14px' }}>Live Incident Feed</span>
          {incidents.length > 0 && (
            <span style={{ background: 'var(--p0-bg)', color: 'var(--p0-color)', borderRadius: '10px', padding: '1px 8px', fontSize: '11px', fontWeight: 700 }}>
              {incidents.filter(i => i.status !== 'CLOSED').length} active
            </span>
          )}
        </div>
        <button className="btn btn-ghost" onClick={onRefresh} disabled={isLoading} style={{ padding: '6px 12px' }}>
          <RefreshCw size={13} style={{ animation: isLoading ? 'spin 0.8s linear infinite' : 'none' }} />
          Refresh
        </button>
      </div>

      {/* Incident list */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {sorted.length === 0 ? (
          <div className="empty-state">
            <AlertTriangle size={40} />
            <h3>No Active Incidents</h3>
            <p>All systems operational. Use the Chaos Simulator to test the system.</p>
          </div>
        ) : (
          sorted.map((incident, i) => (
            <IncidentRow
              key={incident.id}
              incident={incident}
              index={i}
              onClick={() => navigate(`/incidents/${incident.id}`)}
            />
          ))
        )}
      </div>
    </div>
  );
};

const IncidentRow: React.FC<{ incident: WorkItem; index: number; onClick: () => void }> = ({
  incident, index, onClick,
}) => {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="animate-in"
      style={{
        padding: '14px 20px',
        borderBottom: '1px solid var(--border-subtle)',
        cursor: 'pointer',
        background: hovered ? 'var(--bg-elevated)' : 'transparent',
        transition: 'background 0.15s ease',
        animationDelay: `${index * 0.05}s`,
        display: 'flex',
        alignItems: 'center',
        gap: '14px',
      }}
    >
      {/* Severity indicator bar */}
      <div style={{
        width: '3px',
        height: '44px',
        borderRadius: '2px',
        background: {
          P0: 'var(--p0-color)',
          P1: 'var(--p1-color)',
          P2: 'var(--p2-color)',
          P3: 'var(--p3-color)',
        }[incident.severity],
        boxShadow: {
          P0: '0 0 8px var(--p0-glow)',
          P1: '0 0 8px var(--p1-glow)',
          P2: '0 0 8px var(--p2-glow)',
          P3: '0 0 8px var(--p3-glow)',
        }[incident.severity],
        flexShrink: 0,
      }} />

      {/* Main content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
          <SeverityBadge severity={incident.severity} />
          <StatusBadge status={incident.status} />
          <ComponentTypeBadge type={incident.component_type} />
        </div>
        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {incident.title}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px', color: 'var(--text-muted)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Clock size={11} />
            {formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Signal size={11} />
            {incident.signal_count} signals
          </span>
        </div>
      </div>

      <ChevronRight size={14} color="var(--text-muted)" />
    </div>
  );
};
