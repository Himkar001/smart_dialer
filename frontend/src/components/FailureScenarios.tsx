import { useState } from 'react'
import { Zap, AlertTriangle, Users, Copy, Shuffle, CheckCircle2, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import axios from 'axios'

interface Scenario {
  id: string
  label: string
  description: string
  effect: string
  recovery: string
  icon: React.ReactNode
  color: string
  bgColor: string
}

const SCENARIOS: Scenario[] = [
  {
    id: 'provider-outage',
    label: 'Provider Outage',
    description: 'Force Provider B health → 0.1 (Critical)',
    effect: 'Safety Controller REJECTs all calls (approved=0)',
    recovery: 'Auto-recover in 15s — health returns to 0.70',
    icon: <Zap className="h-4 w-4" />,
    color: 'text-red-400',
    bgColor: 'bg-red-500/10 border-red-500/20 hover:bg-red-500/20',
  },
  {
    id: 'worker-crash',
    label: 'Worker Crash',
    description: 'Cancel all in-flight call tasks (simulate process kill)',
    effect: 'Agents stuck in DIALING — crash recovery detects stale agents',
    recovery: 'Emergency release in 3s — Celery re-queues via visibility_timeout',
    icon: <AlertTriangle className="h-4 w-4" />,
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10 border-orange-500/20 hover:bg-orange-500/20',
  },
  {
    id: 'agent-drop',
    label: 'Agent Mass Drop',
    description: 'Force 50% of AVAILABLE agents → OFFLINE',
    effect: 'Dialer automatically places fewer calls (progressive: N:N guarantee)',
    recovery: 'Auto-restore in 20s (simulates shift restart)',
    icon: <Users className="h-4 w-4" />,
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10 border-amber-500/20 hover:bg-amber-500/20',
  },
  {
    id: 'duplicate-storm',
    label: 'Duplicate Storm',
    description: 'Send 5× duplicate RINGING events for every active call',
    effect: 'All absorbed by idempotency_key UNIQUE constraint',
    recovery: 'Instant — zero state changes, calls continue normally',
    icon: <Copy className="h-4 w-4" />,
    color: 'text-violet-400',
    bgColor: 'bg-violet-500/10 border-violet-500/20 hover:bg-violet-500/20',
  },
  {
    id: 'ooo-flood',
    label: 'Out-of-Order Flood',
    description: 'Send COMPLETED before CONNECTED for all RINGING calls',
    effect: 'All rejected by VALID_CALL_TRANSITIONS whitelist',
    recovery: 'Instant — zero state corruption, calls progress normally',
    icon: <Shuffle className="h-4 w-4" />,
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10 border-cyan-500/20 hover:bg-cyan-500/20',
  },
]

interface Props {
  isRunning: boolean
}

export function FailureScenarios({ isRunning }: Props) {
  const [loading, setLoading] = useState<string | null>(null)
  const [triggered, setTriggered] = useState<Record<string, boolean>>({})
  const [result, setResult] = useState<Record<string, string>>({})

  const trigger = async (scenarioId: string) => {
    setLoading(scenarioId)
    try {
      const res = await axios.post(`/api/simulation/trigger/${scenarioId}`)
      setTriggered(prev => ({ ...prev, [scenarioId]: true }))
      setResult(prev => ({ ...prev, [scenarioId]: JSON.stringify(res.data, null, 2) }))
      // Reset triggered marker after 5s
      setTimeout(() => setTriggered(prev => ({ ...prev, [scenarioId]: false })), 5000)
    } catch (e: any) {
      setResult(prev => ({ ...prev, [scenarioId]: e?.response?.data?.detail ?? 'Error' }))
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Failure Scenarios
        </h2>
        {!isRunning && (
          <span className="text-xs text-amber-400 bg-amber-400/10 rounded-full px-2 py-0.5">
            Start simulation first
          </span>
        )}
      </div>

      <div className="space-y-2">
        {SCENARIOS.map(scenario => (
          <div
            key={scenario.id}
            className={cn(
              'rounded-lg border p-3 transition-colors',
              isRunning ? scenario.bgColor : 'bg-muted/30 border-border opacity-60'
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={isRunning ? scenario.color : 'text-muted-foreground'}>
                  {scenario.icon}
                </span>
                <span className="text-sm font-medium">{scenario.label}</span>
                {triggered[scenario.id] && (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                )}
              </div>
              <button
                onClick={() => trigger(scenario.id)}
                disabled={!isRunning || loading === scenario.id}
                className={cn(
                  'rounded-md px-3 py-1 text-xs font-semibold transition-all',
                  isRunning
                    ? 'bg-primary text-primary-foreground hover:bg-primary/80'
                    : 'bg-muted text-muted-foreground cursor-not-allowed',
                  loading === scenario.id && 'opacity-50'
                )}
              >
                {loading === scenario.id
                  ? <Loader2 className="h-3 w-3 animate-spin" />
                  : 'Trigger'}
              </button>
            </div>

            <p className="text-xs text-muted-foreground mt-1.5 ml-6">{scenario.description}</p>

            <div className="mt-2 ml-6 space-y-0.5 text-[10px]">
              <div className="flex gap-1">
                <span className="text-red-400 shrink-0">Effect:</span>
                <span className="text-muted-foreground">{scenario.effect}</span>
              </div>
              <div className="flex gap-1">
                <span className="text-emerald-400 shrink-0">Recovery:</span>
                <span className="text-muted-foreground">{scenario.recovery}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
