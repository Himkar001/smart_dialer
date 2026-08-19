import { useState } from 'react'
import { Play, Square, Zap, Shield } from 'lucide-react'
import { cn } from '@/lib/utils'
import { startSimulation, stopSimulation } from '@/lib/api'

interface Props {
  isRunning: boolean
  onStart: () => void
  onStop: () => void
}

export function SimulationControls({ isRunning, onStart, onStop }: Props) {
  const [agentCount, setAgentCount] = useState(20)
  const [borrowerCount, setBorrowerCount] = useState(100)
  const [mode, setMode] = useState<'PROGRESSIVE' | 'PREDICTIVE'>('PROGRESSIVE')
  const [provider, setProvider] = useState<'PROVIDER_A' | 'PROVIDER_B'>('PROVIDER_A')
  const [loading, setLoading] = useState(false)

  const handleStart = async () => {
    setLoading(true)
    try {
      await startSimulation({ agent_count: agentCount, borrower_count: borrowerCount, mode, provider })
      onStart()
    } catch (e) {
      console.error('Failed to start simulation', e)
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    try {
      await stopSimulation()
      onStop()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
        Simulation Controls
      </h2>

      <div className="space-y-4">
        {/* Agent Count */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-muted-foreground">Agents</span>
            <span className="font-medium">{agentCount}</span>
          </div>
          <input
            type="range" min={5} max={100} value={agentCount}
            onChange={e => setAgentCount(Number(e.target.value))}
            disabled={isRunning}
            className="w-full accent-primary disabled:opacity-50"
          />
        </div>

        {/* Borrower Count */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-muted-foreground">Borrowers</span>
            <span className="font-medium">{borrowerCount}</span>
          </div>
          <input
            type="range" min={20} max={500} step={10} value={borrowerCount}
            onChange={e => setBorrowerCount(Number(e.target.value))}
            disabled={isRunning}
            className="w-full accent-primary disabled:opacity-50"
          />
        </div>

        {/* Mode Toggle */}
        <div>
          <span className="text-sm text-muted-foreground block mb-2">Dialing Mode</span>
          <div className="flex rounded-lg border border-border overflow-hidden">
            {(['PROGRESSIVE', 'PREDICTIVE'] as const).map(m => (
              <button
                key={m}
                onClick={() => setMode(m)}
                disabled={isRunning}
                className={cn(
                  'flex-1 py-1.5 text-sm font-medium transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50',
                  mode === m
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted'
                )}
              >
                {m === 'PROGRESSIVE' ? <Zap className="h-3 w-3" /> : <Shield className="h-3 w-3" />}
                {m === 'PROGRESSIVE' ? 'Progressive' : 'Predictive'}
              </button>
            ))}
          </div>
        </div>

        {/* Provider Toggle */}
        <div>
          <span className="text-sm text-muted-foreground block mb-2">Provider</span>
          <div className="flex rounded-lg border border-border overflow-hidden">
            {(['PROVIDER_A', 'PROVIDER_B'] as const).map(p => (
              <button
                key={p}
                onClick={() => setProvider(p)}
                disabled={isRunning}
                className={cn(
                  'flex-1 py-1.5 text-sm font-medium transition-colors disabled:opacity-50',
                  provider === p
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted'
                )}
              >
                {p === 'PROVIDER_A' ? 'A — Fast & Reliable' : 'B — Slow & Chaotic'}
              </button>
            ))}
          </div>
        </div>

        {/* Start / Stop */}
        <button
          onClick={isRunning ? handleStop : handleStart}
          disabled={loading}
          className={cn(
            'w-full py-2.5 rounded-lg font-semibold flex items-center justify-center gap-2 transition-all',
            isRunning
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-primary hover:bg-primary/90 text-primary-foreground',
            loading && 'opacity-60 cursor-not-allowed'
          )}
        >
          {isRunning
            ? <><Square className="h-4 w-4" /> Stop Simulation</>
            : <><Play className="h-4 w-4" /> Start Simulation</>}
        </button>
      </div>
    </div>
  )
}
