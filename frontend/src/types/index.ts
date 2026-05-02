export interface Signal {
  id: string;
  component_id: string;
  component_type: ComponentType;
  severity: Severity;
  message: string;
  error_code?: string;
  stack_trace?: string;
  metadata: Record<string, unknown>;
  source_host?: string;
  timestamp: string;
  work_item_id?: string;
  ingested_at: string;
}

export interface WorkItem {
  id: string;
  component_id: string;
  component_type: ComponentType;
  severity: Severity;
  title: string;
  status: WorkItemStatus;
  signal_count: number;
  first_signal_id: string;
  assigned_to?: string;
  rca_id?: string;
  mttr_minutes?: number;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface RCA {
  id: string;
  work_item_id: string;
  incident_start: string;
  incident_end: string;
  root_cause_category: RootCauseCategory;
  root_cause_description: string;
  fix_applied: string;
  prevention_steps: string;
  affected_services: string[];
  submitted_by: string;
  mttr_minutes: number;
  created_at: string;
}

export interface StateTransition {
  from_status: WorkItemStatus;
  to_status: WorkItemStatus;
  transitioned_by?: string;
  notes?: string;
  transitioned_at: string;
}

export interface DashboardSummary {
  by_severity: Record<Severity, number>;
  by_status: Record<WorkItemStatus, number>;
  avg_mttr_minutes: number;
  total_active: number;
  signals_per_sec: number;
  recent_incidents: Partial<WorkItem>[];
}

export interface MetricPoint {
  timestamp: number;
  count: number;
}

export type Severity = 'P0' | 'P1' | 'P2' | 'P3';

export type ComponentType =
  | 'RDBMS'
  | 'NOSQL'
  | 'CACHE'
  | 'ASYNC_QUEUE'
  | 'API'
  | 'MCP_HOST'
  | 'LOAD_BALANCER'
  | 'MICROSERVICE';

export type WorkItemStatus = 'OPEN' | 'INVESTIGATING' | 'RESOLVED' | 'CLOSED';

export type RootCauseCategory =
  | 'Infrastructure'
  | 'Code Bug'
  | 'Configuration'
  | 'External Dependency'
  | 'Capacity'
  | 'Network'
  | 'Security'
  | 'Human Error'
  | 'Unknown';

export interface WsMessage {
  event:
    | 'initial_state'
    | 'incident_created'
    | 'status_changed'
    | 'rca_submitted'
    | 'heartbeat'
    | 'pong';
  [key: string]: unknown;
}
