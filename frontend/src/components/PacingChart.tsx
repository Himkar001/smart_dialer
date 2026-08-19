import { useEffect, useRef } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { formatTime } from '@/lib/utils'

interface PacingPoint {
  time: string
  requested: number
  approved: number
  answer_rate: number
  provider_health: number
}

interface Props {
  history: PacingPoint[]
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-xl">
      <p className="font-medium mb-1 text-muted-foreground">{label}</p>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-medium text-foreground">
            {typeof p.value === 'number' && p.value <= 1
              ? `${(p.value * 100).toFixed(1)}%`
              : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export function PacingChart({ history }: Props) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
        Pacing Engine — Live
      </h2>

      {history.length < 2 ? (
        <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
          Waiting for data…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={history} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="time"
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: '11px', color: 'hsl(var(--muted-foreground))' }}
            />
            <Line
              type="monotone" dataKey="requested"
              name="Requested" stroke="#60a5fa" strokeWidth={1.5}
              dot={false} isAnimationActive={false}
            />
            <Line
              type="monotone" dataKey="approved"
              name="Approved" stroke="#34d399" strokeWidth={2}
              dot={false} isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
