import { useEffect, useRef } from 'react'
import { env } from '@/env'
import { HuntEventSchema } from '@/events/schema'
import { useHuntStore } from '@/store/hunt-store'

const BACKOFF_MS = [1_000, 2_000, 5_000, 10_000, 30_000] as const

type Status = 'connecting' | 'connected' | 'reconnecting' | 'closed'

interface UseHuntStreamOptions {
  onStatus?: (status: Status) => void
}

export function useHuntStream(huntId: string | null, options?: UseHuntStreamOptions) {
  const dispatch = useHuntStore((s) => s.dispatch)
  const lastSeqRef = useRef(-1)
  const { onStatus } = options ?? {}

  useEffect(() => {
    if (!huntId) return

    let attempt = 0
    let ws: WebSocket | null = null
    let timer: ReturnType<typeof setTimeout> | null = null
    let dead = false

    function connect() {
      if (dead) return
      onStatus?.('connecting')

      const fromSeq = lastSeqRef.current + 1
      const url = `${env.VITE_GATEWAY_URL}/hunts/${huntId}/stream?from_seq=${fromSeq}`
      ws = new WebSocket(url)

      ws.onopen = () => {
        attempt = 0
        onStatus?.('connected')
      }

      ws.onmessage = ({ data }: MessageEvent<string>) => {
        let raw: unknown
        try {
          raw = JSON.parse(data)
        } catch {
          return
        }
        const result = HuntEventSchema.safeParse(raw)
        if (!result.success) {
          console.warn('[ws] unrecognised event shape', raw)
          return
        }
        lastSeqRef.current = Math.max(lastSeqRef.current, result.data.seq)
        dispatch(result.data)
      }

      ws.onclose = ({ code }) => {
        if (dead || code === 1000) {
          onStatus?.('closed')
          return
        }
        const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)] ?? 30_000
        attempt++
        onStatus?.('reconnecting')
        timer = setTimeout(connect, delay)
      }

      ws.onerror = () => {
        ws?.close()
      }
    }

    connect()

    return () => {
      dead = true
      if (timer !== null) clearTimeout(timer)
      ws?.close(1000)
    }
  }, [huntId, dispatch, onStatus])
}