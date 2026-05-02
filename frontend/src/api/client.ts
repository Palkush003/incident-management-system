import axios from 'axios';
import type { WorkItem, Signal, RCA, DashboardSummary, MetricPoint, StateTransition } from '../types';

const BASE = import.meta.env.VITE_API_URL || '';

export const api = axios.create({
  baseURL: BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Work Items ─────────────────────────────────────────────────────────────

export const getWorkItems = (params?: Record<string, string | number>) =>
  api.get<WorkItem[]>('/api/v1/work-items', { params }).then(r => r.data);

export const getWorkItem = (id: string) =>
  api.get<WorkItem>(`/api/v1/work-items/${id}`).then(r => r.data);

export const getWorkItemSignals = (id: string, limit = 100) =>
  api.get<{ total: number; signals: Signal[] }>(
    `/api/v1/work-items/${id}/signals`, { params: { limit } }
  ).then(r => r.data);

export const getWorkItemTimeline = (id: string) =>
  api.get<StateTransition[]>(`/api/v1/work-items/${id}/timeline`).then(r => r.data);

export const transitionWorkItem = (
  id: string,
  target_status: string,
  assigned_to?: string,
  notes?: string,
) =>
  api.patch<WorkItem>(`/api/v1/work-items/${id}/transition`, {
    target_status, assigned_to, notes,
  }).then(r => r.data);

// ── RCA ────────────────────────────────────────────────────────────────────

export const getRCA = (workItemId: string) =>
  api.get<RCA>(`/api/v1/work-items/${workItemId}/rca`).then(r => r.data);

export const submitRCA = (workItemId: string, data: Omit<RCA, 'id' | 'work_item_id' | 'mttr_minutes' | 'created_at'>) =>
  api.post<RCA>(`/api/v1/work-items/${workItemId}/rca`, data).then(r => r.data);

// ── Dashboard ──────────────────────────────────────────────────────────────

export const getDashboardSummary = () =>
  api.get<DashboardSummary>('/api/v1/dashboard/summary').then(r => r.data);

export const getDashboardMetrics = (seconds = 60) =>
  api.get<{ series: MetricPoint[] }>('/api/v1/dashboard/metrics', { params: { seconds } }).then(r => r.data);

export const getMttrStats = () =>
  api.get('/api/v1/dashboard/mttr-stats').then(r => r.data);

// ── Signals ────────────────────────────────────────────────────────────────

export const ingestSignal = (payload: object) =>
  api.post('/api/v1/signals', payload).then(r => r.data);

export const ingestSignalBatch = (payloads: object[]) =>
  api.post('/api/v1/signals/batch', payloads).then(r => r.data);

// ── Health ─────────────────────────────────────────────────────────────────

export const getHealth = () =>
  api.get('/health').then(r => r.data);

// ── WebSocket ──────────────────────────────────────────────────────────────

export function createWebSocket(): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.VITE_WS_HOST || window.location.host;
  return new WebSocket(`${protocol}//${host}/api/v1/ws`);
}
