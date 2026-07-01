import { Paperclip } from 'lucide-react'
import { MessageBubble } from './message-bubble'
import { PresetCard, PRESETS } from './preset-card'
import { FileChip } from './file-chip'
import { FileDropOverlay } from './file-drop-overlay'
import { useIntakeLogic } from './use-intake'

export default function IntakePage() {
  const {
    messages,
    input,
    setInput,
    attachedFiles,
    removeFile,
    isDragging,
    isPending,
    send,
    pickFiles,
    addFiles,
    fileInputRef,
    textareaRef,
    messagesEndRef,
    handleKeyDown,
    onDragEnter,
    onDragOver,
    onDragLeave,
    onDrop,
  } = useIntakeLogic()

  return (
    <div className="h-screen flex flex-col bg-canvas overflow-hidden">
      {/* Nav */}
      <nav className="h-12 px-5 flex items-center justify-between shrink-0 border-b border-border/20">
        <div className="flex items-center gap-2.5">
          <img src="/pack-logo.svg" className="w-[22px] h-[26px]" alt="Pack" />
          <span className="text-sm font-semibold tracking-wide text-text">The Pack</span>
        </div>
        <button className="p-1 rounded-md hover:bg-surface-raised transition-colors" aria-label="Menu">
          <img src="/icon-menu.svg" className="w-5 h-5 opacity-60" alt="" />
        </button>
      </nav>

      {/* Main */}
      <div
        className="flex-1 overflow-hidden flex flex-col items-center"
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <div className="w-full max-w-[640px] h-full flex flex-col px-4">
          {/* Dynamic spacer */}
          <div className={messages.length === 0 ? 'flex-1' : 'h-10'} />

          {/* Heading */}
          <h1 className="text-[26px] font-semibold text-center text-white leading-snug mb-6 shrink-0">
            What should the pack hunt down?
          </h1>

          {/* Messages */}
          {messages.length > 0 && (
            <div className="flex-1 overflow-y-auto flex flex-col gap-5 pb-4 min-h-0">
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* File chips */}
          {attachedFiles.length > 0 && (
            <div className="flex gap-2 flex-wrap mb-2 shrink-0">
              {attachedFiles.map((f) => (
                <FileChip key={f.localId} file={f} onRemove={removeFile} />
              ))}
            </div>
          )}

          {/* Input bar */}
          <div className="border border-border rounded-xl bg-surface flex items-end gap-2 px-3 py-2.5 mb-3 shrink-0">
            <button
              onClick={pickFiles}
              className="shrink-0 p-1 text-muted hover:text-text transition-colors"
              aria-label="Attach files"
            >
              <Paperclip size={16} />
            </button>

            <textarea
              ref={textareaRef}
              placeholder="Describe your task, or drop a file"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              className="flex-1 bg-transparent resize-none outline-none text-sm text-text
                         placeholder:text-muted max-h-[120px] overflow-y-auto leading-relaxed"
            />

            <button
              className="shrink-0 p-1 text-muted hover:text-text transition-colors"
              aria-label="Voice input"
            >
              <img
                src="/icon-mic.svg"
                className="w-5 h-5"
                style={{ filter: 'brightness(0.5) invert(1)' }}
                alt=""
              />
            </button>

            <button
              onClick={() => void send()}
              disabled={isPending || (input.trim() === '' && attachedFiles.length === 0)}
              className="shrink-0 w-8 h-8 rounded-full bg-[#2563EB] flex items-center justify-center
                         disabled:opacity-30 hover:bg-[#1d4ed8] transition-colors"
              aria-label="Send"
            >
              {isPending ? (
                <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <img
                  src="/icon-send.svg"
                  className="w-4 h-4"
                  style={{ filter: 'brightness(0) invert(1)' }}
                  alt=""
                />
              )}
            </button>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              accept=".pdf,.csv,.txt,.md,.docx,.mp3,.mp4,.wav"
              onChange={(e) => {
                if (e.target.files) addFiles(e.target.files)
                e.target.value = ''
              }}
            />
          </div>

          {/* Preset cards */}
          <div className="grid grid-cols-3 gap-3 pb-6 shrink-0">
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
