interface Props {
  health: Record<string, number> | undefined
}

function HealthRing({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100)
  const color =
    pct >= 70 ? 'text-emerald-400 stroke-emerald-400'
    : pct >= 40 ? 'text-amber-400 stroke-amber-400'
    : 'text-red-400 stroke-red-400'

  const r = 28
  const circumference = 2 * Math.PI * r
  const strokeDash = (pct / 100) * circumference

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative h-20 w-20">
        <svg className="h-20 w-20 -rotate-90" viewBox="0 0 72 72">
          <circle cx="36" cy="36" r={r} fill="none" strokeWidth="6"
            className="stroke-muted" />
          <circle cx="36" cy="36" r={r} fill="none" strokeWidth="6"
            strokeDasharray={`${strokeDash} ${circumference}`}
            strokeLinecap="round"
            className={`transition-all duration-700 ${color.split(' ')[1]}`}
          />
        </svg>
        <span className={`absolute inset-0 flex items-center justify-center text-sm font-bold ${color.split(' ')[0]}`}>
          {pct}%
        </span>
      </div>
      <span className="text-xs text-muted-foreground font-medium">{label}</span>
    </div>
  )
}

export function ProviderHealth({ health }: Props) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
        Provider Health
      </h2>
      <div className="flex justify-around">
        <HealthRing score={health?.['PROVIDER_A'] ?? 0} label="Provider A" />
        <HealthRing score={health?.['PROVIDER_B'] ?? 0} label="Provider B" />
      </div>
      <div className="mt-4 space-y-1 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-full bg-emerald-400" />≥70% — Healthy</div>
        <div className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-full bg-amber-400" />40–69% — Degraded</div>
        <div className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-full bg-red-400" />&lt;40% — Critical</div>
      </div>
    </div>
  )
}
