import React, { useState } from 'react';
import { CheckCircle, XCircle, Loader, FileText } from 'lucide-react';
import { submitRCA } from '../api/client';
import type { RCA, RootCauseCategory } from '../types';

const ROOT_CAUSE_CATEGORIES: RootCauseCategory[] = [
  'Infrastructure', 'Code Bug', 'Configuration', 'External Dependency',
  'Capacity', 'Network', 'Security', 'Human Error', 'Unknown',
];

interface RCAFormProps {
  workItemId: string;
  onSuccess: (rca: RCA) => void;
  existingRCA?: RCA;
}

export const RCAForm: React.FC<RCAFormProps> = ({ workItemId, onSuccess, existingRCA }) => {
  const [form, setForm] = useState({
    incident_start: existingRCA?.incident_start?.slice(0, 16) ?? '',
    incident_end: existingRCA?.incident_end?.slice(0, 16) ?? '',
    root_cause_category: existingRCA?.root_cause_category ?? 'Infrastructure' as RootCauseCategory,
    root_cause_description: existingRCA?.root_cause_description ?? '',
    fix_applied: existingRCA?.fix_applied ?? '',
    prevention_steps: existingRCA?.prevention_steps ?? '',
    affected_services: existingRCA?.affected_services?.join(', ') ?? '',
    submitted_by: existingRCA?.submitted_by ?? '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const mttrPreview = () => {
    if (!form.incident_start || !form.incident_end) return null;
    const diff = new Date(form.incident_end).getTime() - new Date(form.incident_start).getTime();
    if (diff <= 0) return null;
    const mins = Math.round(diff / 60000);
    if (mins < 60) return `${mins}m`;
    return `${Math.floor(mins / 60)}h ${mins % 60}m`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const rca = await submitRCA(workItemId, {
        incident_start: new Date(form.incident_start).toISOString(),
        incident_end: new Date(form.incident_end).toISOString(),
        root_cause_category: form.root_cause_category,
        root_cause_description: form.root_cause_description,
        fix_applied: form.fix_applied,
        prevention_steps: form.prevention_steps,
        affected_services: form.affected_services.split(',').map(s => s.trim()).filter(Boolean),
        submitted_by: form.submitted_by,
      });
      setSuccess(true);
      onSuccess(rca);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Submission failed. Please try again.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <CheckCircle size={48} color="var(--accent-green)" style={{ marginBottom: '16px' }} />
        <h3 style={{ color: 'var(--accent-green)', marginBottom: '8px' }}>RCA Submitted Successfully</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          MTTR: <strong>{mttrPreview()}</strong>. You can now close this incident.
        </p>
      </div>
    );
  }

  const mttr = mttrPreview();

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
        <FileText size={16} color="var(--accent-blue)" />
        <h3 style={{ fontSize: '15px', fontWeight: 700 }}>Root Cause Analysis</h3>
        <span style={{ fontSize: '11px', color: 'var(--p0-color)', background: 'var(--p0-bg)', padding: '2px 8px', borderRadius: '10px', fontWeight: 600 }}>REQUIRED TO CLOSE</span>
      </div>

      {/* Time window */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div className="form-group">
          <label className="form-label">Incident Start *</label>
          <input
            type="datetime-local"
            className="form-input"
            value={form.incident_start}
            onChange={e => setForm(f => ({ ...f, incident_start: e.target.value }))}
            required
          />
        </div>
        <div className="form-group">
          <label className="form-label">Incident End *</label>
          <input
            type="datetime-local"
            className="form-input"
            value={form.incident_end}
            onChange={e => setForm(f => ({ ...f, incident_end: e.target.value }))}
            required
          />
        </div>
      </div>

      {/* MTTR Preview */}
      {mttr && (
        <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: 'var(--radius-md)', padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Calculated MTTR:</span>
          <span style={{ color: 'var(--accent-green)', fontWeight: 700, fontSize: '18px', fontFamily: 'var(--font-mono)' }}>{mttr}</span>
        </div>
      )}

      {/* Root cause category */}
      <div className="form-group">
        <label className="form-label">Root Cause Category *</label>
        <select
          className="form-select"
          value={form.root_cause_category}
          onChange={e => setForm(f => ({ ...f, root_cause_category: e.target.value as RootCauseCategory }))}
          required
        >
          {ROOT_CAUSE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Root cause description */}
      <div className="form-group">
        <label className="form-label">Root Cause Description * <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'none' }}>(min 20 chars)</span></label>
        <textarea
          className="form-textarea"
          placeholder="Describe the technical root cause in detail. What went wrong and why?"
          value={form.root_cause_description}
          onChange={e => setForm(f => ({ ...f, root_cause_description: e.target.value }))}
          minLength={20}
          required
          style={{ minHeight: '100px' }}
        />
        <span style={{ fontSize: '11px', color: form.root_cause_description.length >= 20 ? 'var(--accent-green)' : 'var(--text-muted)', textAlign: 'right' }}>
          {form.root_cause_description.length} chars
        </span>
      </div>

      {/* Fix applied */}
      <div className="form-group">
        <label className="form-label">Fix Applied * <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'none' }}>(min 10 chars)</span></label>
        <textarea
          className="form-textarea"
          placeholder="What immediate action was taken to resolve the incident?"
          value={form.fix_applied}
          onChange={e => setForm(f => ({ ...f, fix_applied: e.target.value }))}
          minLength={10}
          required
        />
      </div>

      {/* Prevention steps */}
      <div className="form-group">
        <label className="form-label">Prevention Steps * <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'none' }}>(min 10 chars)</span></label>
        <textarea
          className="form-textarea"
          placeholder="What changes will prevent this from happening again? (e.g., monitoring, code changes, process improvements)"
          value={form.prevention_steps}
          onChange={e => setForm(f => ({ ...f, prevention_steps: e.target.value }))}
          minLength={10}
          required
        />
      </div>

      {/* Affected services */}
      <div className="form-group">
        <label className="form-label">Affected Services <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'none' }}>(comma-separated, optional)</span></label>
        <input
          type="text"
          className="form-input"
          placeholder="api-gateway, user-service, payment-service"
          value={form.affected_services}
          onChange={e => setForm(f => ({ ...f, affected_services: e.target.value }))}
        />
      </div>

      {/* Submitted by */}
      <div className="form-group">
        <label className="form-label">Submitted By *</label>
        <input
          type="text"
          className="form-input"
          placeholder="Your name or email"
          value={form.submitted_by}
          onChange={e => setForm(f => ({ ...f, submitted_by: e.target.value }))}
          required
        />
      </div>

      {/* Error */}
      {error && (
        <div style={{ background: 'var(--p0-bg)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', padding: '12px 16px', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
          <XCircle size={16} color="var(--p0-color)" style={{ flexShrink: 0, marginTop: '1px' }} />
          <span style={{ color: 'var(--p0-color)', fontSize: '13px' }}>{error}</span>
        </div>
      )}

      <button type="submit" className="btn btn-primary" disabled={loading}>
        {loading ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Submitting...</> : '✓ Submit Root Cause Analysis'}
      </button>
    </form>
  );
};
