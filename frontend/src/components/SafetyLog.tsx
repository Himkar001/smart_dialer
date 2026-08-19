import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

interface SafetyEntry {
  time: string
  action: string
  reason: string
  approved: number
  requested: number
}

interface Props {
  entries: SafetyEntry[]
}

const ACTION_STYLE: Record<string, string> = {
  APPROVE:  'text-emerald-400 bg-emerald-400/10',
  REDUCE:   'text-amber-400 bg-amber-400/10',
  REJECT:   'text-red-400 bg-red-400/10',
  FALLBACK: 'text-orange-400 bg-orange-400/10',
}

export function SafetyLog({ entries }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Safety Controller Log
        </h2>
        <span className="text-xs text-muted-foreground">{entries.length} decisions</span>
      </div>

      <div className="h-48 overflow-y-auto space-y-1.5 pr-1">
        {entries.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            No decisions yet — start a simulation
          </div>
        ) : (
          entries.slice(-50).map((e, i) => (
            <div key={i} className="flex items-start gap-2 text-xs rounded-md bg-muted/40 p-2">
              <span className="text-muted-foreground shrink-0 tabular-nums">{e.time}</span>
              <span className={cn(
                'shrink-0 rounded px-1.5 py-0.5 font-semibold text-[10px]',
                ACTION_STYLE[e.action] ?? 'text-slate-400 bg-slate-400/10'
              )}>
                {e.action}
              </span>
              <span className="text-muted-foreground truncate flex-1">{e.reason}</span>
              <span className="shrink-0 tabular-nums text-foreground">
                {e.approved}/{e.requested}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
