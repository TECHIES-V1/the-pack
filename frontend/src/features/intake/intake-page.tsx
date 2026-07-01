import { ChevronDown, Pause, Play, Plus, Square, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MessageBubble } from './message-bubble'
import { PresetCard, PRESETS } from './preset-card'
import { FileCard } from './file-chip'
import { FileDropOverlay } from './file-drop-overlay'
import { useIntakeLogic } from './use-intake'
import { useMicRecorder } from './use-mic-recorder'

const MODES = ['Signal', 'Patrol', 'Scout'] as const
type Mode = (typeof MODES)[number]

const AUDIO_EXTS = new Set(['mp3', 'wav', 'ogg', 'aac', 'flac', 'm4a', 'webm'])
function isAudio(name: string) {
  return AUDIO_EXTS.has(name.split('.').pop()?.toLowerCase() ?? '')
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

// Bubbly rounded-rectangle bar. Live bars (fixed=false) vary width with volume.
// Playback bars (fixed=true) use constant width so 40 bars fill the row evenly.
// No CSS transition — at 60fps React updates the style every 16ms; transitions
// would compound and trail behind the audio, making it look laggier.
function Bar({ h, color, fixed = false }: { h: number; color: string; fixed?: boolean }) {
  const height = Math.max(4, h * 34)
  const width = fixed ? 3 : Math.max(3, 3 + h * 3)
  return (
    <div
      className="shrink-0"
      style={{ width, height, borderRadius: width, backgroundColor: color }}
    />
  )
}

// Live bars during recording — reacts to real mic levels at ~60fps
function LiveBars({ getLiveBars }: { getLiveBars: () => number[] }) {
  const [bars, setBars] = useState<number[]>(() => Array(40).fill(0))
  const rafRef = useRef<number>(0)

  useEffect(() => {
    const tick = () => {
      setBars(getLiveBars())
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [getLiveBars])

  return (
    <div className="flex-1 flex items-center gap-[3px] h-9 overflow-hidden">
      {bars.map((h, i) => (
        <Bar key={i} h={h} color={`rgba(255,255,255,${0.25 + h * 0.75})`} />
      ))}
    </div>
  )
}

export default function IntakePage() {
  const [mode, setMode] = useState<Mode>('Signal')
  const [showModeMenu, setShowModeMenu] = useState(false)
  const modeMenuRef = useRef<HTMLDivElement>(null)

  // Voice recorder state
  const [voicePeaks, setVoicePeaks] = useState<number[]>([])
  const [isPlaying, setIsPlaying] = useState(false)
  const [playProgress, setPlayProgress] = useState(0)
  const [playDuration, setPlayDuration] = useState(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const playRafRef = useRef<number>(0)

  const {
    messages, input, setInput, attachedFiles, removeFile,
    isDragging, isPending, send, pickFiles, addFiles,
    fileInputRef, textareaRef, messagesEndRef, handleKeyDown,
    onDragEnter, onDragOver, onDragLeave, onDrop,
  } = useIntakeLogic()

  const handleRecordingComplete = useCallback((file: File, peaks: number[]) => {
    addFiles([file])
    setVoicePeaks(peaks)
  }, [addFiles])

  const { isRecording, toggle: toggleMic, getLiveBars, recordingSeconds } =
    useMicRecorder(handleRecordingComplete)

  const hasMessages = messages.length > 0
  const audioFile = attachedFiles.find(f => isAudio(f.name))
  const docFiles = attachedFiles.filter(f => !isAudio(f.name))

  const audioUrl = useMemo(() => {
    if (!audioFile) return null
    return URL.createObjectURL(audioFile.file)
  }, [audioFile])

  useEffect(() => {
    return () => { if (audioUrl) URL.revokeObjectURL(audioUrl) }
  }, [audioUrl])

  // Close mode menu on click outside
  useEffect(() => {
    if (!showModeMenu) return
    const close = (e: MouseEvent) => {
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target as Node)) {
        setShowModeMenu(false)
      }
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [showModeMenu])

  // Reset all voice state when audio file is removed
  useEffect(() => {
    if (!audioFile) {
      audioRef.current?.pause()
      cancelAnimationFrame(playRafRef.current)
      setIsPlaying(false)
      setPlayProgress(0)
      setPlayDuration(0)
      setVoicePeaks([])
    }
  }, [audioFile])

  const startTracking = useCallback(() => {
    const tick = () => {
      const el = audioRef.current
      if (el && !el.paused && el.duration > 0) {
        setPlayProgress(el.currentTime / el.duration)
        playRafRef.current = requestAnimationFrame(tick)
      }
    }
    playRafRef.current = requestAnimationFrame(tick)
  }, [])

  const togglePlay = useCallback(() => {
    const el = audioRef.current
    if (!el) return
    if (isPlaying) {
      el.pause()
      cancelAnimationFrame(playRafRef.current)
      setIsPlaying(false)
    } else {
      void el.play()
      setIsPlaying(true)
      startTracking()
    }
  }, [isPlaying, startTracking])

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const el = audioRef.current
    if (!el || !el.duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    el.currentTime = ratio * el.duration
    setPlayProgress(ratio)
  }, [])

  const discardVoiceMemo = useCallback(() => {
    if (audioFile) removeFile(audioFile.localId)
    cancelAnimationFrame(playRafRef.current)
    setIsPlaying(false)
    setPlayProgress(0)
    setPlayDuration(0)
    setVoicePeaks([])
  }, [audioFile, removeFile])

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: '#0a0a0a' }}
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {/* Nav */}
      <nav className="h-[52px] flex items-stretch shrink-0">
        <div className="flex items-center gap-3 px-5" style={{ backgroundColor: '#1a1a1a' }}>
          <img src="/pack-logo.svg" className="w-[22px] h-[26px]" alt="Pack" />
          <span className="text-sm font-semibold text-white tracking-wide">The Pack</span>
          <button className="p-1 opacity-70 hover:opacity-100 transition-opacity" aria-label="Menu">
            <img src="/icon-menu.svg" className="w-5 h-5" alt="" />
          </button>
        </div>
      </nav>

      {/* Content */}
      <div
        className={`flex-1 flex px-4 ${
          hasMessages ? 'flex-col items-center py-6' : 'items-center justify-center pb-10'
        }`}
      >
        <div className="w-full max-w-[700px] flex flex-col gap-6">

          <h1 className="text-[30px] font-semibold text-white text-center leading-tight">
            What should the pack hunt down?
          </h1>

          {hasMessages && (
            <div className="flex flex-col gap-5 overflow-y-auto max-h-[40vh] min-h-0">
              {messages.map((m) => <MessageBubble key={m.id} message={m} />)}
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* Input box */}
          <div
            className="rounded-2xl px-5 pt-4 pb-3 shrink-0"
            style={{ backgroundColor: '#111111', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            {docFiles.length > 0 && (
              <div className="flex gap-3 flex-wrap mb-4">
                {docFiles.map((f) => (
                  <FileCard key={f.localId} file={f} onRemove={removeFile} />
                ))}
              </div>
            )}

            <textarea
              ref={textareaRef}
              placeholder="Describe your task, or drop a file"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              className="w-full bg-transparent resize-none outline-none text-sm text-white
                         placeholder:text-[#555] max-h-[120px] overflow-y-auto leading-relaxed"
            />

            {isRecording ? (
              /* ── Recording: red dot + timer + live bars + stop ── */
              <div className="flex items-center gap-3 mt-3">
                <div className="flex items-center gap-2 shrink-0">
                  <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  <span className="text-red-400 text-sm font-mono tabular-nums">
                    {formatTime(recordingSeconds)}
                  </span>
                </div>

                <LiveBars getLiveBars={getLiveBars} />

                <button
                  onClick={toggleMic}
                  className="text-[#888] hover:text-white transition-colors shrink-0"
                  aria-label="Stop recording"
                >
                  <Square size={16} />
                </button>
              </div>

            ) : audioFile ? (
              /* ── Playback: play/pause + real waveform + time + delete + send ── */
              <>
                <audio
                  ref={audioRef}
                  src={audioUrl ?? undefined}
                  onEnded={() => {
                    cancelAnimationFrame(playRafRef.current)
                    setIsPlaying(false)
                    setPlayProgress(0)
                  }}
                  onLoadedMetadata={(e) => {
                    setPlayDuration((e.target as HTMLAudioElement).duration)
                  }}
                />
                <div className="flex items-center gap-3 mt-3">
                  <button
                    onClick={togglePlay}
                    className="text-[#888] hover:text-white transition-colors shrink-0"
                    aria-label={isPlaying ? 'Pause' : 'Play'}
                  >
                    {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                  </button>

                  {/* Real waveform from decoded audio, tappable to seek.
                      justify-between distributes 40 fixed-width bars evenly
                      so they fill the full container with no dead space. */}
                  <div
                    className="flex-1 flex items-center justify-between h-9 overflow-hidden cursor-pointer"
                    onClick={handleSeek}
                  >
                    {voicePeaks.map((h, i) => (
                      <Bar
                        key={i}
                        h={h}
                        fixed
                        color={i / voicePeaks.length <= playProgress
                          ? 'rgba(255,255,255,0.9)'
                          : 'rgba(255,255,255,0.18)'}
                      />
                    ))}
                  </div>

                  <span className="text-[#555] text-xs font-mono tabular-nums shrink-0">
                    {formatTime(Math.floor(playProgress * playDuration))} / {formatTime(Math.floor(playDuration))}
                  </span>

                  <button
                    onClick={discardVoiceMemo}
                    className="text-[#666] hover:text-white transition-colors shrink-0"
                    aria-label="Delete recording"
                  >
                    <X size={16} />
                  </button>

                  <button
                    onClick={() => void send()}
                    disabled={isPending}
                    className="w-9 h-9 rounded-full bg-white flex items-center justify-center
                               disabled:opacity-30 hover:bg-gray-200 transition-colors shrink-0"
                    aria-label="Send"
                  >
                    {isPending
                      ? <span className="w-3 h-3 border-2 border-gray-800 border-t-transparent rounded-full animate-spin" />
                      : <img src="/icon-send.svg" className="w-4 h-4" alt="" />
                    }
                  </button>
                </div>
              </>

            ) : (
              /* ── Normal action row ── */
              <div className="flex items-center gap-3 mt-3">
                <button
                  onClick={pickFiles}
                  className="text-[#666] hover:text-white transition-colors shrink-0"
                  aria-label="Attach files"
                >
                  <Plus size={18} />
                </button>

                <div className="flex-1" />

                <div className="relative" ref={modeMenuRef}>
                  <button
                    onClick={() => setShowModeMenu((v) => !v)}
                    className="flex items-center gap-1 text-sm text-[#888] hover:text-white transition-colors"
                  >
                    <span>{mode}</span>
                    <ChevronDown size={13} />
                  </button>
                  {showModeMenu && (
                    <div
                      className="absolute bottom-full right-0 mb-2 rounded-xl py-1 z-20 min-w-[120px] shadow-xl"
                      style={{ backgroundColor: '#1C1C1C', border: '1px solid rgba(255,255,255,0.08)' }}
                    >
                      {MODES.map((opt) => (
                        <button
                          key={opt}
                          onClick={() => { setMode(opt); setShowModeMenu(false) }}
                          className="w-full text-left px-3.5 py-2 text-sm text-[#ccc] hover:bg-white/5 transition-colors"
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <button
                  onClick={toggleMic}
                  className="text-[#888] hover:text-white transition-colors shrink-0"
                  aria-label="Record voice"
                >
                  <img src="/icon-mic.svg" className="w-5 h-5" alt="" />
                </button>

                <button
                  onClick={() => void send()}
                  disabled={isPending || (input.trim() === '' && attachedFiles.length === 0)}
                  className="w-9 h-9 rounded-full bg-white flex items-center justify-center
                             disabled:opacity-30 hover:bg-gray-200 transition-colors shrink-0"
                  aria-label="Send"
                >
                  {isPending
                    ? <span className="w-3 h-3 border-2 border-gray-800 border-t-transparent rounded-full animate-spin" />
                    : <img src="/icon-send.svg" className="w-4 h-4" alt="" />
                  }
                </button>
              </div>
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            hidden
            accept=".pdf,.csv,.txt,.md,.docx,.mp3,.wav,.ogg,.aac,.flac,.m4a"
            onChange={(e) => {
              if (e.target.files) addFiles(e.target.files)
              e.target.value = ''
            }}
          />

          <div className="grid grid-cols-3 gap-3">
            {PRESETS.map((p) => (
              <PresetCard key={p.id} preset={p} onClick={() => setInput(p.prompt)} />
            ))}
          </div>
        </div>
      </div>

      {isDragging && <FileDropOverlay />}
    </div>
  )
}
