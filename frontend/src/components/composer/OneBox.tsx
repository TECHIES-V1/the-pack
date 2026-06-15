import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { MicSheet } from "./MicSheet";

type Mode = "Signal" | "On Wild" | "On Command";
const MODES: Mode[] = ["Signal", "On Wild", "On Command"];

interface AttachedFile {
  id: string;
  name: string;
  status: "uploading" | "ready";
}

interface OneBoxProps {
  droppedFiles?: File[];
  prefill?: string;
  onFilesAdded?: (files: File[]) => void;
  onFileRemoved?: (name: string) => void;
  onFolderRejected?: () => void;
  onSubmit?: (payload: { text: string; attachments: AttachedFile[]; mode: Mode }) => void;
  onRecordingChange?: (recording: boolean) => void;
}

export function OneBox({ droppedFiles = [], prefill, onFilesAdded, onFileRemoved, onFolderRejected, onSubmit, onRecordingChange }: OneBoxProps) {
  const [value, setValue] = useState("");
  const [recording, setRecording] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [attachments, setAttachments] = useState<AttachedFile[]>([]);
  const [mode, setMode] = useState<Mode>("Signal");
  const [modeOpen, setModeOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const processedIds = useRef<Set<string>>(new Set());

  const addFiles = useCallback((files: File[]) => {
    const newFiles: File[] = [];
    for (const file of files) {
      const id = `${file.name}-${file.size}`;
      if (processedIds.current.has(id)) continue;
      processedIds.current.add(id);
      newFiles.push(file);
      setAttachments((prev) => [...prev, { id, name: file.name, status: "uploading" }]);
      setTimeout(() => {
        setAttachments((prev) =>
          prev.map((f) => (f.id === id ? { ...f, status: "ready" } : f))
        );
      }, 1200);
    }
    if (newFiles.length > 0) onFilesAdded?.(newFiles);
  }, [onFilesAdded]);

  useEffect(() => {
    if (prefill) {
      setValue(prefill);
      textareaRef.current?.focus();
    }
  }, [prefill]);

  useEffect(() => {
    if (droppedFiles.length === 0) return;
    addFiles(droppedFiles);
  }, [droppedFiles, addFiles]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setModeOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const all = Array.from(e.target.files ?? []);
    const files = all.filter((f) => !(f.size === 0 && f.type === ""));
    if (files.length < all.length) onFolderRejected?.();
    if (files.length > 0) addFiles(files);
    e.target.value = "";
  }

  function removeAttachment(id: string) {
    const removed = attachments.find((f) => f.id === id);
    processedIds.current.delete(id);
    setAttachments((prev) => prev.filter((f) => f.id !== id));
    if (removed) onFileRemoved?.(removed.name);
  }

  function handleSubmit() {
    if (submitting || !canSubmit) return;
    setSubmitting(true);
    setTimeout(() => {
      onSubmit?.({ text: value, attachments, mode });
    }, 900);
  }

  const canSubmit = value.trim().length > 0 || attachments.length > 0;

  return (
    <div className="w-[min(880px,90vw)] bg-door-surface border border-door-border rounded-2xl px-4 pt-3.5 pb-3 flex flex-col gap-4">
      <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileChange} />

      {/* File tiles — above textarea */}
      <AnimatePresence>
        {attachments.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="flex gap-3 flex-wrap"
          >
            {attachments.map((file) => (
              <motion.div
                key={file.id}
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85 }}
                transition={{ duration: 0.18 }}
                className="flex flex-col items-center gap-1 w-16"
              >
                <div
                  className="relative w-16 h-16 rounded-xl flex items-center justify-center"
                  style={{ background: file.status === "uploading" ? "#2a2a2a" : "#e03a2f" }}
                >
                  {file.status === "uploading" ? (
                    /* Asterisk-style spinner matching the design */
                    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" className="animate-spin text-[#888]">
                      <line x1="11" y1="2" x2="11" y2="7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      <line x1="11" y1="15" x2="11" y2="20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      <line x1="2" y1="11" x2="7" y2="11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      <line x1="15" y1="11" x2="20" y2="11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      <line x1="4.22" y1="4.22" x2="7.76" y2="7.76" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      <line x1="14.24" y1="14.24" x2="17.78" y2="17.78" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      <line x1="17.78" y1="4.22" x2="14.24" y2="7.76" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      <line x1="7.76" y1="14.24" x2="4.22" y2="17.78" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                  ) : (
                    <>
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white">
                        <path d="M6 2h9l5 5v15a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                        <path d="M15 2v5h5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <button
                        onClick={() => removeAttachment(file.id)}
                        className="absolute -top-1.5 -left-1.5 w-5 h-5 rounded-full bg-black flex items-center justify-center cursor-pointer border-none"
                      >
                        <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                          <path d="M1 1l6 6M7 1L1 7" stroke="white" strokeWidth="1.4" strokeLinecap="round" />
                        </svg>
                      </button>
                    </>
                  )}
                </div>
                <span className="text-[11px] text-door-dim truncate w-full text-center">
                  {file.name.length > 8 ? file.name.slice(0, 7) + "…" : file.name}
                </span>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Textarea row */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onInput={handleInput}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && canSubmit) {
            e.preventDefault();
            handleSubmit();
          }
        }}
        placeholder="What should the pack hunt down?"
        rows={1}
        className="w-full bg-transparent border-none outline-none resize-none text-white text-[15px] font-sans leading-relaxed p-0 overflow-hidden placeholder:text-door-dim"
      />

      {/* Bottom toolbar row */}
      <div className="flex items-center gap-2">
        {/* Plus — hidden when recording */}
        <AnimatePresence>
          {!recording && (
            <motion.button
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.15 }}
              onClick={() => fileInputRef.current?.click()}
              className="bg-transparent border-none text-white cursor-pointer p-0 flex items-center shrink-0 overflow-hidden"
            >
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
                <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </motion.button>
          )}
        </AnimatePresence>

        {/* Waveform — shown inline when recording, takes full space */}
        <AnimatePresence>
          {recording && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="flex-1 overflow-hidden"
            >
              <MicSheet onTranscript={setValue} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Spacer when not recording */}
        {!recording && <div className="flex-1" />}

        {/* Right side actions */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Signal mode dropdown — hidden when recording */}
          <div className="relative" ref={dropdownRef}
            style={{ display: recording ? "none" : undefined }}
          >
            <button
              onClick={() => setModeOpen((o) => !o)}
              className="flex items-center gap-1 text-white text-[13px] font-sans bg-transparent border-none cursor-pointer px-1 py-0.5"
            >
              {mode}
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className={`transition-transform duration-150 ${modeOpen ? "rotate-180" : ""}`}>
                <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            <AnimatePresence>
              {modeOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -6, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -6, scale: 0.97 }}
                  transition={{ duration: 0.15 }}
                  className="absolute bottom-full right-0 mb-2 bg-door-surface border border-door-border rounded-xl overflow-hidden min-w-[148px] z-20"
                >
                  <p className="text-[11px] text-door-dim px-3 pt-2.5 pb-1 m-0 uppercase tracking-wider">Mode selector</p>
                  {MODES.map((m) => (
                    <button
                      key={m}
                      onClick={() => { setMode(m); setModeOpen(false); }}
                      className="w-full flex items-center justify-between px-3 py-2 text-[13px] text-white bg-transparent border-none cursor-pointer hover:bg-white/5 font-sans text-left"
                    >
                      {m}
                      {m === mode && (
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <path d="M2 7l3.5 3.5L12 3" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Mic / cancel recording */}
          <button
            onClick={() => setRecording((r) => { const next = !r; onRecordingChange?.(next); return next; })}
            className="bg-transparent border-none text-white cursor-pointer p-0 flex items-center"
          >
            {recording ? (
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
                <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
                <rect x="7" y="2" width="6" height="10" rx="3" stroke="currentColor" strokeWidth="1.6" />
                <path d="M4 10a6 6 0 0012 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                <path d="M10 16v2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            )}
          </button>

          {/* Submit */}
          <motion.button
            onClick={handleSubmit}
            disabled={!canSubmit || submitting}
            whileTap={canSubmit ? { scale: 0.92 } : {}}
            className={`w-9 h-9 rounded-full border-none flex items-center justify-center shrink-0 transition-colors duration-200 ${canSubmit && !submitting
              ? "bg-white text-door-bg cursor-pointer"
              : "bg-door-border text-door-dim cursor-default"
              }`}
          >
            {submitting ? (
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="animate-spin">
                <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="2" strokeDasharray="28" strokeDashoffset="10" strokeLinecap="round" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 12V4M4 8l4-4 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </motion.button>
        </div>
      </div>
    </div>
  );
}
