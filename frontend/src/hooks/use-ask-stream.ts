import { useState, useCallback, useRef } from 'react'
import { env } from '@/env'

interface UseAskStreamResult {
  answer: string
  streaming: boolean
  ask: (huntId: string, question: string) => Promise<void>
  reset: () => void
}

export function useAskStream(): UseAskStreamResult {
  const [answer, setAnswer] = useState('')
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setAnswer('')
    setStreaming(false)
  }, [])

  const ask = useCallback(async (huntId: string, question: string) => {
    abortRef.current?.abort()
    const abort = new AbortController()
    abortRef.current = abort

    setAnswer('')
    setStreaming(true)

    try {
      const res = await fetch(`${env.VITE_ENGINE_URL}/hunts/${huntId}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
        signal: abort.signal,
      })

      if (!res.ok || !res.body) {
        throw new Error(`ask/stream failed: ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''

        for (const part of parts) {
          if (!part.startsWith('data:')) continue
          const json = part.slice('data:'.length).trim()
          if (!json || json === '[DONE]') continue
          try {
            const msg = JSON.parse(json) as { type: string; text?: string }
            if (msg.type === 'token' && msg.text) {
              setAnswer((prev) => prev + msg.text)
            }
          } catch {
            // malformed SSE line — skip
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('[ask-stream]', err)
      }
    } finally {
      setStreaming(false)
    }
  }, [])

  return { answer, streaming, ask, reset }
}