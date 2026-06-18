/**
 * Single shared WebSocket to /ws/events. Pushes payloads into the zustand
 * `live` slice. Reconnects with bounded backoff. Heartbeats are dropped.
 */
import { useEffect, useRef } from 'react'
import { useAppStore } from '@/lib/store'
import type { LiveEvent } from '@/lib/types'

const MAX_BACKOFF_MS = 15_000

export function useEventStream(enabled = true) {
  const pushLiveEvent = useAppStore((s) => s.pushLiveEvent)
  const setWsState    = useAppStore((s) => s.setWsState)
  const isAuthenticated = useAppStore((s) => s.isAuthenticated)
  const wsRef         = useRef<WebSocket | null>(null)
  const backoffRef    = useRef<number>(1000)
  const closedByUser  = useRef<boolean>(false)

  useEffect(() => {
    if (!enabled || !isAuthenticated) return
    closedByUser.current = false

    function connect() {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const host = window.location.host || 'localhost:8000'
      const url = `${proto}://${host}/ws/events`
      
      let ws: WebSocket
      try {
        ws = new WebSocket(url)
      } catch (e) {
        console.error('WebSocket connection failed:', e)
        setWsState('error')
        return
      }
      
      wsRef.current = ws

      ws.onopen = () => {
        backoffRef.current = 1000
        setWsState('live')
      }
      ws.onerror = () => setWsState('error')
      ws.onclose = () => {
        if (closedByUser.current) return
        setWsState('reconnecting')
        const wait = backoffRef.current
        backoffRef.current = Math.min(wait * 2, MAX_BACKOFF_MS)
        setTimeout(connect, wait)
      }
      ws.onmessage = (msg) => {
        let parsed: unknown
        try { parsed = JSON.parse(msg.data as string) } catch { return }
        if (!parsed || typeof parsed !== 'object') return
        const obj = parsed as { heartbeat?: boolean; event?: LiveEvent } & LiveEvent
        if (obj.heartbeat) return
        const payload: LiveEvent | undefined = obj.event ?? (obj as LiveEvent)
        if (!payload || !payload.event_id) return
        pushLiveEvent(payload)
      }
    }

    connect()
    return () => {
      closedByUser.current = true
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [enabled, pushLiveEvent, setWsState])
}
