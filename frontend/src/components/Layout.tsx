import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, AlertTriangle, Activity, Zap,
  Radio, Settings, ChevronRight
} from 'lucide-react';

interface SidebarProps {
  wsStatus: 'connecting' | 'connected' | 'disconnected';
  activeIncidents: number;
}

export const Layout: React.FC<{ children: React.ReactNode; wsStatus: 'connecting' | 'connected' | 'disconnected'; activeIncidents?: number }> = ({
  children, wsStatus, activeIncidents = 0,
}) => {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
    { icon: AlertTriangle, label: 'Incidents', path: '/incidents' },
    { icon: Activity, label: 'Metrics', path: '/metrics' },
    { icon: Zap, label: 'Chaos Simulator', path: '/chaos' },
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>⚡ IMS</h1>
          <p>Incident Management System</p>
        </div>

        <nav className="sidebar-nav">
          {navItems.map(({ icon: Icon, label, path }) => (
            <button
              key={path}
              className={`nav-item ${location.pathname === path ? 'active' : ''}`}
              onClick={() => navigate(path)}
            >
              <Icon size={16} />
              <span>{label}</span>
              {label === 'Incidents' && activeIncidents > 0 && (
                <span style={{
                  marginLeft: 'auto',
                  background: 'var(--p0-bg)',
                  color: 'var(--p0-color)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  borderRadius: '10px',
                  padding: '1px 8px',
                  fontSize: '11px',
                  fontWeight: 700,
                }}>
                  {activeIncidents}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Connection status */}
        <div style={{ padding: '16px', borderTop: '1px solid var(--border-subtle)' }}>
          <div className={`status-indicator status-${wsStatus === 'connected' ? 'healthy' : wsStatus === 'connecting' ? 'degraded' : 'unhealthy'}`}>
            <div className="status-dot" />
            <span>
              {wsStatus === 'connected' ? 'Live Feed Active' :
               wsStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {wsStatus !== 'connected' && (
          <div className={`ws-banner ${wsStatus}`}>
            <Radio size={12} />
            {wsStatus === 'connecting'
              ? 'Connecting to live feed...'
              : '⚠ Live feed disconnected — reconnecting...'}
          </div>
        )}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
          {children}
        </div>
      </main>
    </div>
  );
};
