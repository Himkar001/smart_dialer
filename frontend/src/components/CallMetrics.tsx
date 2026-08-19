import { CallMetrics as CallMetricsType } from '@/types'
import { cn } from '@/lib/utils'

interface StatCard {
  label: string
  key: keyof CallMetricsType
  color: string
  textColor: string
}

const CARDS: StatCard[] = [
  { label: 'Completed', key: 'completed', color: 'bg-emerald-500/10', textColor: 'text-emerald-400' },
  { label: 'Connected', key: 'connected', color: 'bg-violet-500/10',  textColor: 'text-violet-400'  },
  { label: 'Ringing',   key: 'ringing',   color: 'bg-cyan-500/10',    textColor: 'text-cyan-400'    },
  { label: 'Initiated', key: 'initiated', color: 'bg-blue-500/10',    textColor: 'text-blue-400'    },
  { label: 'Failed',    key: 'failed',    color: 'bg-red-500/10',     textColor: 'text-red-400'     },
  { label: 'Queued',    key: 'queued',    color: 'bg-slate-500/10',   textColor: 'text-slate-400'   },
]

interface Props {
  calls: CallMetricsType | undefined
}

export function CallMetrics({ calls }: Props) {
  const total = calls
    ? Object.values(calls).reduce((a, b) => a + b, 0)
    : 0

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Call Metrics
        </h2>
        <span className="text-2xl font-bold">{total}</span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {CARDS.map(({ label, key, color, textColor }) => (
          <div key={key} className={cn('rounded-lg p-3 text-center', color)}>
            <div className={cn('text-xl font-bold tabular-nums', textColor)}>
              {calls?.[key] ?? 0}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
