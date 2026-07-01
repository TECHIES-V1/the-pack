import { useCallback, useEffect, useRef, useState } from 'react'

const N_BARS = 40

async function extractPeaks(file: File): Promise<number[]> {
  const ctx = new AudioContext()
  try {
    const buf = await ctx.decodeAudioData(await file.arrayBuffer())
    const ch = buf.getChannelData(0)
    const block = Math.floor(ch.length / N_BARS)
    const peaks = Array.from({ length: N_BARS }, (_, i) => {
      let max = 0
      const end = Math.min((i + 1) * block, ch.length)
      for (let j = i * block; j < end; j++) {
        const v = Math.abs(ch[j])
        if (v > max) max = v
      }
      return max
    })
    const globalMax = Math.max(...peaks, 0.001)
    return peaks.map(p => p / globalMax)
  } finally {
    await ctx.close()
  }
}

export function useMicRecorder(onComplete: (file: File, peaks: number[]) => void) {
  const [isRecording, setIsRecording] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const analyserRef = useRef<AnalyserNode | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const dataRef = useRef<Uint8Array | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mountedRef = useRef(true)

  // Returns N_BARS normalized bars (0–1) using frequency data.
  // Frequency magnitudes are naturally high for voice (100–200/255) giving visually
  // active bars, unlike time-domain which gives tiny deviations (~10–30/128).
  // We focus on the voice frequency range (first 40% of bins ≈ 0–8 kHz).
  const getLiveBars = useCallback((): number[] => {
    const analyser = analyserRef.current
    const data = dataRef.current
    if (!analyser || !data) return Array(N_BARS).fill(0)
    analyser.getByteFrequencyData(data)
    const voiceBins = Math.floor(data.length * 0.4)
    const blockSize = Math.max(1, Math.floor(voiceBins / N_BARS))
    return Array.from({ length: N_BARS }, (_, i) => {
      let max = 0
      const end = Math.min((i + 1) * blockSize, voiceBins)
      for (let j = i * blockSize; j < end; j++) {
        if (data[j] > max) max = data[j]
      }
      return max / 255
    })
  }, [])

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      const audioCtx = new AudioContext()
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 2048
      analyser.smoothingTimeConstant = 0.75
      audioCtx.createMediaStreamSource(stream).connect(analyser)
      analyserRef.current = analyser
      audioCtxRef.current = audioCtx
      // frequencyBinCount = fftSize / 2 = 1024; getByteFrequencyData fills this many elements
      dataRef.current = new Uint8Array(analyser.frequencyBinCount)

      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg'
      const recorder = new MediaRecorder(stream, { mimeType })
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        void audioCtxRef.current?.close()
        analyserRef.current = null
        audioCtxRef.current = null
        dataRef.current = null
        if (timerRef.current) clearInterval(timerRef.current)
        timerRef.current = null
        setRecordingSeconds(0)
        setIsRecording(false)

        const blob = new Blob(chunksRef.current, { type: mimeType })
        const ext = mimeType.includes('webm') ? 'webm' : 'ogg'
        const file = new File([blob], `voice-${Date.now()}.${ext}`, { type: mimeType })

        extractPeaks(file)
          .then(peaks => { if (mountedRef.current) onComplete(file, peaks) })
          .catch(() => { if (mountedRef.current) onComplete(file, Array(N_BARS).fill(0.5)) })
      }

      recorder.start()
      recorderRef.current = recorder
      setRecordingSeconds(0)
      setIsRecording(true)

      timerRef.current = setInterval(() => {
        setRecordingSeconds(s => s + 1)
      }, 1000)
    } catch (err) {
      console.error('[mic] permission denied or unavailable', err)
    }
  }, [onComplete])

  const stop = useCallback(() => {
    recorderRef.current?.stop()
    recorderRef.current = null
  }, [])

  const toggle = useCallback(() => {
    if (isRecording) stop()
    else void start()
  }, [isRecording, start, stop])

  useEffect(() => {
    return () => {
      mountedRef.current = false
      if (timerRef.current) clearInterval(timerRef.current)
      void audioCtxRef.current?.close()
    }
  }, [])

  return { isRecording, toggle, getLiveBars, recordingSeconds }
}
