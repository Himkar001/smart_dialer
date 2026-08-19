import { useEffect, useRef, useState } from 'react'
import { Phone, Moon, Sun, Wifi, WifiOff, Loader2, TrendingUp } from 'lucide-react'
import { useMetrics } from '@/hooks/useMetrics'
import { AgentPool } from '@/components/AgentPool'
import { CallMetrics } from '@/components/CallMetrics'
import { SimulationControls } from '@/components/SimulationControls'
import { ProviderHealth } from '@/components/ProviderHealth'
import { PacingChart } from '@/components/PacingChart'
import { SafetyLog } from '@/components/SafetyLog'
import { cn, formatTime, safetyActionColor } from '@/lib/utils'

type Theme = 'dark' | 'light'

interface PacingPoint {
  time: string
  requested: number
  approved: number
  answer_rate: number
  provider_health: number
}

interface SafetyEntry {
  time: string
  action: string
  reason: string
  approved: number
  requested: number
}

function ConnectionBadge({ status }: { status: string }) {
  if (status === 'connected')
    return <div className="flex items-center gap-1.5 text-xs text-emerald-400"><Wifi className="h-3.5 w-3.5" />Live</div>
  if (status === 'connecting')
    return <div className="flex items-center gap-1.5 text-xs text-amber-400"><Loader2 className="h-3.5 w-3.5 animate-spin" />Connecting</div>
  return <div className="flex items-center gap-1.5 text-xs text-red-400"><WifiOff className="h-3.5 w-3.5" />Offline</div>
}

export default function App() {
  const [theme, setTheme] = useState<Theme>('dark')
  const [simRunning, setSimRunning] = useState(false)
  const { metrics, wsStatus } = useMetrics()

  // Rolling history for pacing chart (last 30 points)
  const [pacingHistory, setPacingHistory] = useState<PacingPoint[]>([])
  const [safetyLog, setSafetyLog] = useState<SafetyEntry[]>([])
  const lastDecision = useRef<string | null>(null)

  useEffect(() => { document.documentElement.className = theme }, [theme])

  // Update pacing history when metrics arrive
  useEffect(() => {
    if (!metrics) return
    const pacing = metrics.pacing
    if (!pacing) return

    const point: PacingPoint = {
      time: new Date(metrics.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      requested: pacing.dial_count_requested ?? 0,
      approved:  pacing.dial_count_approved ?? 0,
      answer_rate: pacing.answer_rate ?? 0,
      provider_health: pacing.provider_health ?? 0,
    }
    setPacingHistory(prev => [...prev.slice(-29), point])

    // Append to safety log on new decision
    const decision = metrics.safety?.last_decision
    const reason = metrics.safety?.last_reason
    if (decision && reason && decision !== lastDecision.current) {
      lastDecision.current = decision
      setSafetyLog(prev => [...prev.slice(-99), {
        time: new Date(metrics.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        action: decision,
        reason,
        approved: pacing.dial_count_approved ?? 0,
        requested: pacing.dial_count_requested ?? 0,
      }])
    }
  }, [metrics])

  const abandonedRate = metrics?.safety?.abandoned_rate ?? 0
  const abandonedPct = (abandonedRate * 100).toFixed(1)
  const answerRate = metrics?.pacing?.answer_rate ?? 0
  const answerPct = (answerRate * 100).toFixed(1)
  const sampleSize = (metrics?.pacing as any)?.sample_size ?? 0
  const lastAction = metrics?.safety?.last_decision
  const mode = metrics?.pacing?.mode ?? 'PROGRESSIVE'

  const activeCalls = (metrics?.calls.initiated ?? 0) + (metrics?.calls.ringing ?? 0) + (metrics?.calls.connected ?? 0)

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="flex h-14 items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Phone className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-semibold tracking-tight">SmartDialer</span>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">v1.0.0</span>
          </div>

          <div className="flex items-center gap-3">
            {simRunning && (
              <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                {mode} — Running
              </div>
            )}
            {lastAction && (
              <div className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', safetyActionColor(lastAction as any))}>
                {lastAction}
              </div>
            )}
            <div className={cn(
              'rounded-full px-2.5 py-0.5 text-xs font-medium',
              abandonedRate > 0.03 ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'
            )}>
              Abandoned: {abandonedPct}%
            </div>
            <ConnectionBadge status={wsStatus} />
            <button
              onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* ── Main ──────────────────────────────────────────────────── */}
      <main className="p-6 max-w-screen-2xl mx-auto">

        {/* KPI Strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-5">
          {[
            { label: 'Available',    value: metrics?.agents.available ?? '—',  color: 'text-emerald-400' },
            { label: 'Active Calls', value: activeCalls,                        color: 'text-violet-400'  },
            { label: 'Completed',    value: metrics?.calls.completed ?? '—',   color: 'text-blue-400'    },
            { label: 'Failed',       value: metrics?.calls.failed ?? '—',      color: abandonedRate > 0.03 ? 'text-red-400' : 'text-slate-400' },
            { label: 'Answer Rate',  value: sampleSize > 0 ? `${answerPct}%` : 'N/A', color: answerRate > 0.6 ? 'text-emerald-400' : 'text-amber-400' },
            { label: 'Mode',         value: mode,                               color: mode === 'PREDICTIVE' ? 'text-violet-400' : 'text-sky-400' },
          ].map(kpi => (
            <div key={kpi.label} className="rounded-xl border border-border bg-card px-4 py-3">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">{kpi.label}</p>
              <p className={cn('text-xl font-bold tabular-nums', kpi.color)}>{kpi.value}</p>
            </div>
          ))}
        </div>

        {/* Main grid: 4 columns on large screens */}
        <div className="grid gap-4 lg:grid-cols-4">

          {/* Col 1: Controls + Provider Health */}
          <div className="space-y-4">
            <SimulationControls
              isRunning={simRunning}
              onStart={() => setSimRunning(true)}
              onStop={() => setSimRunning(false)}
            />
            <ProviderHealth health={metrics?.provider_health} />
          </div>

          {/* Col 2: Agent Pool */}
          <div className="space-y-4">
            <AgentPool agents={metrics?.agents} />

            {/* Answer Rate Tracker */}
            <div className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">Answer Rate Tracker</h3>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Rate</span>
                  <span className={cn('font-bold', answerRate > 0.6 ? 'text-emerald-400' : 'text-amber-400')}>
                    {sampleSize > 0 ? `${answerPct}%` : 'Cold start…'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Samples</span>
                  <span className="font-medium">{sampleSize} / 10 min</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Status</span>
                  <span className={cn('text-xs font-medium rounded-full px-2 py-0.5',
                    sampleSize >= 10 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
                  )}>
                    {sampleSize >= 10 ? 'Warm' : 'Cold Start'}
                  </span>
                </div>
                {sampleSize < 10 && (
                  <div className="mt-2 h-1.5 w-full rounded-full bg-muted">
                    <div
                      className="h-1.5 rounded-full bg-amber-400 transition-all"
                      style={{ width: `${(sampleSize / 10) * 100}%` }}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Col 3: Call Metrics + Pacing Chart */}
          <div className="space-y-4">
            <CallMetrics calls={metrics?.calls} />
            <PacingChart history={pacingHistory} />
          </div>

          {/* Col 4: Safety Log + Pacing info */}
          <div className="space-y-4">
            <SafetyLog entries={safetyLog} />

            {/* Safety decision detail */}
            <div className="rounded-xl border border-border bg-card p-4">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Safety Rules (Priority Order)
              </h3>
              <div className="space-y-2 text-xs">
                {[
                  { action: 'FALLBACK', rule: 'Abandoned > 3%', color: 'text-orange-400' },
                  { action: 'REJECT',   rule: 'Health < 0.40',  color: 'text-red-400'    },
                  { action: 'REDUCE',   rule: 'Health < 0.70 or ratio > 3×', color: 'text-amber-400' },
                  { action: 'APPROVE',  rule: 'All thresholds met',           color: 'text-emerald-400' },
                ].map((row, i) => (
                  <div key={row.action} className={cn(
                    'flex items-center gap-2 rounded p-1.5',
                    lastAction === row.action ? 'bg-muted' : ''
                  )}>
                    <span className="text-muted-foreground w-4">{i + 1}.</span>
                    <span className={cn('font-semibold w-16', row.color)}>{row.action}</span>
                    <span className="text-muted-foreground">{row.rule}</span>
                    {lastAction === row.action && (
                      <div className="ml-auto h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Empty state */}
        {!simRunning && !metrics?.agents.total && (
          <div className="mt-6 rounded-xl border border-dashed border-border p-10 text-center">
            <Phone className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <h3 className="text-lg font-semibold mb-1">No simulation running</h3>
            <p className="text-sm text-muted-foreground">
              Select mode, agents, provider — then click <strong>Start Simulation</strong>
            </p>
          </div>
        )}
      </main>
    </div>
  )
}
