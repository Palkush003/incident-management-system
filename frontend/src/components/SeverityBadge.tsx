import React from 'react';
import type { Severity, WorkItemStatus } from '../types';

interface SeverityBadgeProps { severity: Severity; showPulse?: boolean; }

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity, showPulse = true }) => {
  const needsPulse = showPulse && (severity === 'P0' || severity === 'P1');
  return (
    <span className={`badge badge-${severity.toLowerCase()}`}>
      {needsPulse && (
        <span className={`pulse-dot pulse-dot-${severity.toLowerCase()}`} />
      )}
      {severity}
    </span>
  );
};

interface StatusBadgeProps { status: WorkItemStatus; }

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => (
  <span className={`badge badge-${status.toLowerCase().replace('_', '-')}`}>
    {status}
  </span>
);

export const ComponentTypeBadge: React.FC<{ type: string }> = ({ type }) => (
  <span style={{
    background: 'rgba(6, 182, 212, 0.1)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(6, 182, 212, 0.2)',
    borderRadius: '4px',
    padding: '2px 8px',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: 'var(--font-mono)',
  }}>
    {type}
  </span>
);
