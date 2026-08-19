import { useEffect, useState } from 'react'
import { Phone, Activity, Shield, Zap, Server, AlertTriangle, Moon, Sun } from 'lucide-react'
import { getHealth } from '@/lib/api'

type Theme = 'dark' | 'light'

function App() {
  const [theme, setTheme] = useState<Theme>('dark')
  const [apiStatus, setApiStatus] = useState<'checking' | 'ok' | 'error'>('checking')

  // Apply theme to <html> element
  useEffect(() => {
    document.documentElement.className = theme
  }, [theme])

  // Check API health on mount
  useEffect(() => {
    getHealth()
      .then(() => setApiStatus('ok'))
      .catch(() => setApiStatus('error'))
  }, [])

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="flex h-14 items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Phone className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-semibold tracking-tight">SmartDialer</span>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              v1.0.0
            </span>
          </div>

          <div className="flex items-center gap-4">
            {/* API Status Indicator */}
            <div className="flex items-center gap-1.5 text-sm">
              <div
                className={`h-2 w-2 rounded-full ${
                  apiStatus === 'ok'
                    ? 'bg-emerald-400 animate-pulse'
                    : apiStatus === 'error'
                    ? 'bg-red-400'
                    : 'bg-amber-400 animate-pulse'
                }`}
              />
              <span className="text-muted-foreground text-xs">
                {apiStatus === 'ok' ? 'API Connected' : apiStatus === 'error' ? 'API Offline' : 'Connecting…'}
              </span>
            </div>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* Main content area */}
      <main className="p-6">
        {/* Sprint 1 — Foundation complete banner */}
        <div className="mb-8 rounded-xl border border-border bg-card p-6">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10">
              <Activity className="h-6 w-6 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                Sprint 1 — Foundation Complete ✅
              </h1>
              <p className="mt-1 text-muted-foreground">
                Database schema, state machines, and API are ready. Dashboard panels will be built in Sprint 2–3.
              </p>
            </div>
          </div>
        </div>

        {/* Component Preview Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">

          {/* Progressive Dialer Card */}
          <div className="rounded-xl border border-border bg-card p-5 hover:border-primary/50 transition-colors">
            <div className="flex items-center gap-3 mb-3">
              <div className="rounded-lg bg-blue-500/10 p-2">
                <Zap className="h-5 w-5 text-blue-400" />
              </div>
              <h2 className="font-semibold">Progressive Dialer</h2>
              <span className="ml-auto rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">
                Sprint 2
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              Strict 1:1 agent-to-call mapping. Never dials more calls than available agents.
            </p>
            <div className="mt-4 flex gap-2">
              <span className="rounded-md bg-muted px-2 py-1 text-xs">SELECT FOR UPDATE</span>
              <span className="rounded-md bg-muted px-2 py-1 text-xs">SKIP LOCKED</span>
            </div>
          </div>

          {/* Safety Controller Card */}
          <div className="rounded-xl border border-border bg-card p-5 hover:border-primary/50 transition-colors">
            <div className="flex items-center gap-3 mb-3">
              <div className="rounded-lg bg-orange-500/10 p-2">
                <Shield className="h-5 w-5 text-orange-400" />
              </div>
              <h2 className="font-semibold">Safety Controller</h2>
              <span className="ml-auto rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">
                Sprint 3
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              Mandatory gate between pacing engine and telecom. Cannot be bypassed.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {['APPROVE', 'REDUCE', 'REJECT', 'FALLBACK'].map(a => (
                <span key={a} className="rounded-md bg-muted px-2 py-1 text-xs">{a}</span>
              ))}
            </div>
          </div>

          {/* Failure Scenarios Card */}
          <div className="rounded-xl border border-border bg-card p-5 hover:border-primary/50 transition-colors">
            <div className="flex items-center gap-3 mb-3">
              <div className="rounded-lg bg-red-500/10 p-2">
                <AlertTriangle className="h-5 w-5 text-red-400" />
              </div>
              <h2 className="font-semibold">Failure Scenarios</h2>
              <span className="ml-auto rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">
                Sprint 4
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              5 failure scenarios triggerable from the dashboard.
            </p>
            <div className="mt-4 space-y-1">
              {['Worker Crash', 'Provider Outage', 'Agent Drop', 'Duplicate Events', 'Out-of-Order'].map(s => (
                <div key={s} className="flex items-center gap-2 text-xs text-muted-foreground">
                  <div className="h-1.5 w-1.5 rounded-full bg-red-400" />
                  {s}
                </div>
              ))}
            </div>
          </div>

          {/* State Machine Status */}
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5 md:col-span-2 lg:col-span-3">
            <div className="flex items-center gap-3 mb-4">
              <div className="rounded-lg bg-emerald-500/10 p-2">
                <Server className="h-5 w-5 text-emerald-400" />
              </div>
              <h2 className="font-semibold">Sprint 1 Deliverables</h2>
              <span className="ml-auto rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-400 font-medium">
                ✓ Complete
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { label: 'Agent State Machine', detail: '7 states · SELECT FOR UPDATE SKIP LOCKED' },
                { label: 'Call State Machine', detail: '9 states · Idempotent · Out-of-order guard' },
                { label: 'PostgreSQL Schema', detail: '5 tables · indexes · constraints' },
                { label: 'FastAPI Routes', detail: '/agents · /calls · /campaigns · /health' },
              ].map(item => (
                <div key={item.label} className="rounded-lg bg-card border border-border p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    <span className="text-sm font-medium">{item.label}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Agent State Flow Diagram */}
        <div className="mt-4 rounded-xl border border-border bg-card p-6">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
            Agent Lifecycle
          </h2>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {[
              { state: 'OFFLINE',    color: 'bg-slate-500' },
              null,
              { state: 'AVAILABLE',  color: 'bg-emerald-500' },
              null,
              { state: 'RESERVED',   color: 'bg-sky-400' },
              null,
              { state: 'DIALING',    color: 'bg-blue-500' },
              null,
              { state: 'CONNECTED',  color: 'bg-violet-500' },
              null,
              { state: 'WRAP_UP',    color: 'bg-amber-400' },
            ].map((item, i) =>
              item === null ? (
                <span key={i} className="text-muted-foreground">→</span>
              ) : (
                <span
                  key={item.state}
                  className={`${item.color} rounded-md px-2.5 py-1 text-xs font-medium text-white`}
                >
                  {item.state}
                </span>
              )
            )}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            <strong className="text-foreground">Concurrency safety:</strong>{' '}
            <code className="rounded bg-muted px-1 py-0.5">SELECT ... FOR UPDATE SKIP LOCKED</code>{' '}
            ensures no two workers can ever reserve the same agent simultaneously.
          </p>
        </div>
      </main>
    </div>
  )
}

export default App
