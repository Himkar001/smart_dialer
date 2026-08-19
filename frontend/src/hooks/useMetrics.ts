import { MetricsSnapshot } from '@/types'
import { useWebSocket } from './useWebSocket'

const WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ??
  `ws://${window.location.hostname}:8000/ws/metrics`

export function useMetrics() {
  const { data, status } = useWebSocket<MetricsSnapshot>(WS_URL)
  return { metrics: data, wsStatus: status }
}
