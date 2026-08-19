import { AgentMetrics, AgentState } from '@/types'
import { agentStateColor, cn } from '@/lib/utils'

const STATES: { key: keyof AgentMetrics; label: string; state: AgentState }[] = [
  { key: 'available', label: 'Available',  state: 'AVAILABLE'  },
  { key: 'dialing',   label: 'Dialing',    state: 'DIALING'    },
  { key: 'connected', label: 'Connected',  state: 'CONNECTED'  },
  { key: 'reserved',  label: 'Reserved',   state: 'RESERVED'   },
  { key: 'wrap_up',   label: 'Wrap-Up',    state: 'WRAP_UP'    },
  { key: 'paused',    label: 'Paused',     state: 'PAUSED'     },
  { key: 'offline',   label: 'Offline',    state: 'OFFLINE'    },
]

interface Props {
  agents: AgentMetrics | undefined
}

export function AgentPool({ agents }: Props) {
  const total = agents?.total ?? 0

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Agent Pool
        </h2>
        <span className="text-2xl font-bold">{total}</span>
      </div>

      {/* Stacked progress bar */}
      {total > 0 && (
        <div className="flex h-3 w-full overflow-hidden rounded-full mb-4">
          {STATES.map(({ key, state }) => {
            const count = agents?.[key] ?? 0
            const pct = total > 0 ? (count / total) * 100 : 0
            if (pct === 0) return null
            return (
              <div
                key={key}
                className={cn(agentStateColor(state), 'transition-all duration-700')}
                style={{ width: `${pct}%` }}
                title={`${state}: ${count}`}
              />
            )
          })}
        </div>
      )}

      {/* State breakdown rows */}
      <div className="space-y-2">
        {STATES.map(({ key, label, state }) => {
          const count = agents?.[key] ?? 0
          const pct = total > 0 ? ((count / total) * 100).toFixed(0) : '0'
          return (
            <div key={key} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={cn('h-2.5 w-2.5 rounded-full', agentStateColor(state))} />
                <span className="text-sm text-muted-foreground">{label}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{pct}%</span>
                <span className="w-8 text-right text-sm font-medium tabular-nums">{count}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
