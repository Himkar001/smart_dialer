/** TypeScript types matching the backend Pydantic schemas. */

export type AgentState =
  | 'OFFLINE'
  | 'AVAILABLE'
  | 'RESERVED'
  | 'DIALING'
  | 'CONNECTED'
  | 'WRAP_UP'
  | 'PAUSED'

export type CallState =
  | 'QUEUED'
  | 'RESERVED'
  | 'INITIATED'
  | 'RINGING'
  | 'ANSWERED'
  | 'CONNECTED'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'

export type CampaignMode = 'PROGRESSIVE' | 'PREDICTIVE'
export type CampaignState = 'DRAFT' | 'ACTIVE' | 'PAUSED' | 'COMPLETED'
export type ProviderType = 'PROVIDER_A' | 'PROVIDER_B'
export type SafetyAction = 'APPROVE' | 'REDUCE' | 'REJECT' | 'FALLBACK'

export interface Agent {
  id: string
  name: string
  state: AgentState
  campaign_id: string | null
  reserved_at: string | null
  heartbeat_at: string | null
  created_at: string
  updated_at: string
}

export interface Campaign {
  id: string
  name: string
  mode: CampaignMode
  state: CampaignState
  provider: ProviderType
  max_retries: number
  created_at: string
  updated_at: string
}

export interface CallEvent {
  id: string
  event_type: string
  idempotency_key: string
  raw_payload: Record<string, unknown> | null
  processed_at: string
}

export interface Call {
  id: string
  campaign_id: string
  agent_id: string | null
  borrower_id: string
  state: CallState
  provider: string
  provider_call_id: string | null
  attempt: number
  initiated_at: string | null
  connected_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  events: CallEvent[]
}

// WebSocket metrics payload
export interface AgentMetrics {
  total: number
  offline: number
  available: number
  reserved: number
  dialing: number
  connected: number
  wrap_up: number
  paused: number
}

export interface CallMetrics {
  queued: number
  initiated: number
  ringing: number
  connected: number
  completed: number
  failed: number
  cancelled: number
}

export interface PacingMetrics {
  mode: CampaignMode
  dial_count_requested: number
  dial_count_approved: number
  answer_rate: number
  provider_health: number
}

export interface SafetyDecision {
  action: SafetyAction
  reason: string
  approved_count: number
  timestamp: string
}

export interface MetricsSnapshot {
  timestamp: string
  agents: AgentMetrics
  calls: CallMetrics
  pacing: PacingMetrics
  safety: {
    last_decision: SafetyAction | null
    last_reason: string | null
    abandoned_rate: number
  }
}
