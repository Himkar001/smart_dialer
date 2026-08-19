import { useEffect, useState } from 'react'
import { Phone, Moon, Sun, Wifi, WifiOff, Loader2 } from 'lucide-react'
import { useMetrics } from '@/hooks/useMetrics'
import { AgentPool } from '@/components/AgentPool'
import { CallMetrics } from '@/components/CallMetrics'
import { SimulationControls } from '@/components/SimulationControls'
import { ProviderHealth } from '@/components/ProviderHealth'
import { cn } from '@/lib/utils'

type Theme = 'dark' | 'light'

function ConnectionBadge({ status }: { status: string }) {
  if (status === 'connected')
    return (
      <div className="flex items-center gap-1.5 text-xs text-emerald-400">
        <Wifi className="h-3.5 w-3.5" />Live
      </div>
    )
  if (status === 'connecting')
    return (
      <div className="flex items-center gap-1.5 text-xs text-amber-400">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />Connecting
      </div>
    )
  return (
    <div className="flex items-center gap-1.5 text-xs text-red-400">
      <WifiOff className="h-3.5 w-3.5" />Offline
    </div>
  )
}

export default function App() {
  const [theme, setTheme] = useState<Theme>('dark')
  const [simRunning, setSimRunning] = useState(false)
  const { metrics, wsStatus } = useMetrics()

  useEffect(() => {
    document.documentElement.className = theme
  }, [theme])

  const abandonedRate = metrics?.safety?.abandoned_rate ?? 0
  const abandonedPct = (abandonedRate * 100).toFixed(1)

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="flex h-14 items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Phone className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-semibold tracking-tight">SmartDialer</span>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">v1.0.0</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Live status */}
            {simRunning && (
              <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                Simulation Running
              </div>
            )}

            <ConnectionBadge status={wsStatus} />

            {/* Abandoned rate pill */}
            <div className={cn(
              'rounded-full px-2.5 py-0.5 text-xs font-medium',
              abandonedRate > 0.03
                ? 'bg-red-500/10 text-red-400'
                : 'bg-emerald-500/10 text-emerald-400'
            )}>
              Abandoned: {abandonedPct}%
            </div>

            <button
              onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* ── Main Grid ──────────────────────────────────────────── */}
      <main className="p-6 max-w-screen-xl mx-auto">

        {/* Top KPI strip */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            {
              label: 'Available Agents',
              value: metrics?.agents.available ?? '—',
              sub: `of ${metrics?.agents.total ?? 0} total`,
              color: 'text-emerald-400',
            },
            {
              label: 'Active Calls',
              value: (metrics?.calls.ringing ?? 0) + (metrics?.calls.connected ?? 0) + (metrics?.calls.initiated ?? 0),
              sub: 'initiated + ringing + connected',
              color: 'text-violet-400',
            },
            {
              label: 'Completed',
              value: metrics?.calls.completed ?? '—',
              sub: 'calls finished successfully',
              color: 'text-blue-400',
            },
            {
              label: 'Failed',
              value: metrics?.calls.failed ?? '—',
              sub: `${abandonedPct}% abandoned rate`,
              color: abandonedRate > 0.03 ? 'text-red-400' : 'text-slate-400',
            },
          ].map(kpi => (
            <div key={kpi.label} className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground mb-1">{kpi.label}</p>
              <p className={cn('text-3xl font-bold tabular-nums', kpi.color)}>{kpi.value}</p>
              <p className="text-xs text-muted-foreground mt-1">{kpi.sub}</p>
            </div>
          ))}
        </div>

        {/* Main content */}
        <div className="grid gap-4 lg:grid-cols-3">

          {/* Left column — controls + provider health */}
          <div className="space-y-4">
            <SimulationControls
              isRunning={simRunning}
              onStart={() => setSimRunning(true)}
              onStop={() => setSimRunning(false)}
            />
            <ProviderHealth health={metrics?.provider_health} />
          </div>

          {/* Middle column — agent pool */}
          <div className="space-y-4">
            <AgentPool agents={metrics?.agents} />

            {/* Agent lifecycle explainer */}
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Agent Lifecycle
              </p>
              <div className="flex flex-wrap gap-1.5 text-xs">
                {[
                  { label: 'OFFLINE',   color: 'bg-slate-500'   },
                  { label: '→',         color: ''               },
                  { label: 'AVAILABLE', color: 'bg-emerald-500' },
                  { label: '→',         color: ''               },
                  { label: 'RESERVED',  color: 'bg-sky-400'     },
                  { label: '→',         color: ''               },
                  { label: 'DIALING',   color: 'bg-blue-500'    },
                  { label: '→',         color: ''               },
                  { label: 'CONNECTED', color: 'bg-violet-500'  },
                  { label: '→',         color: ''               },
                  { label: 'WRAP_UP',   color: 'bg-amber-400'   },
                ].map((item, i) =>
                  item.color === '' ? (
                    <span key={i} className="text-muted-foreground">→</span>
                  ) : (
                    <span key={item.label} className={cn(item.color, 'rounded px-1.5 py-0.5 text-white font-medium')}>
                      {item.label}
                    </span>
                  )
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                <code className="rounded bg-muted px-1 text-[10px]">SELECT FOR UPDATE SKIP LOCKED</code>
                {' '}prevents double-reservation
              </p>
            </div>
          </div>

          {/* Right column — call metrics */}
          <div className="space-y-4">
            <CallMetrics calls={metrics?.calls} />

            {/* Call flow explainer */}
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                Call State Machine
              </p>
              <div className="space-y-1 text-xs">
                {[
                  { from: 'QUEUED', to: 'INITIATED', note: 'Allocator places call' },
                  { from: 'INITIATED', to: 'RINGING', note: 'Provider event' },
                  { from: 'RINGING', to: 'ANSWERED', note: 'Borrower picks up' },
                  { from: 'ANSWERED', to: 'CONNECTED', note: 'Agent patched in' },
                  { from: 'CONNECTED', to: 'COMPLETED', note: 'Call ends' },
                  { from: 'ANY', to: 'FAILED', note: 'Idempotent + out-of-order safe' },
                ].map(row => (
                  <div key={row.from} className="flex items-center gap-2">
                    <span className="w-20 text-muted-foreground truncate">{row.from}</span>
                    <span className="text-muted-foreground">→</span>
                    <span className="w-20 text-foreground">{row.to}</span>
                    <span className="text-muted-foreground truncate">{row.note}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>

        {/* No data empty state */}
        {!simRunning && !metrics?.agents.total && (
          <div className="mt-8 rounded-xl border border-dashed border-border p-12 text-center">
            <Phone className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <h3 className="text-lg font-semibold mb-1">No simulation running</h3>
            <p className="text-sm text-muted-foreground">
              Configure agents and borrowers above, then click <strong>Start Simulation</strong>
            </p>
          </div>
        )}
      </main>
    </div>
  )
}
