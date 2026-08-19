import { useCallback, useEffect, useRef, useState } from 'react'

type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export function useWebSocket<T>(url: string) {
  const [data, setData] = useState<T | null>(null)
  const [status, setStatus] = useState<WebSocketStatus>('connecting')
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout>>()
  const retryDelay = useRef(1000)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('connected')
        retryDelay.current = 1000 // Reset backoff on success
      }

      ws.onmessage = (event) => {
        try {
          setData(JSON.parse(event.data) as T)
        } catch {
          // ignore malformed JSON
        }
      }

      ws.onerror = () => {
        setStatus('error')
      }

      ws.onclose = () => {
        setStatus('disconnected')
        // Exponential backoff reconnect (max 10s)
        retryRef.current = setTimeout(() => {
          retryDelay.current = Math.min(retryDelay.current * 1.5, 10_000)
          setStatus('connecting')
          connect()
        }, retryDelay.current)
      }
    } catch {
      setStatus('error')
    }
  }, [url])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { data, status }
}
