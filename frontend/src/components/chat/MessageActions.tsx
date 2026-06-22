// Per-message hover toolbar — the table-stakes actions every AI chat ships: copy, regenerate the
// last reply, edit & resend a prompt, and 👍/👎 feedback. Shown on hover of a message row (the
// parent gives the row a `group` class).

import { useEffect, useRef, useState } from "react";
import {
  LuCopy,
  LuCheck,
  LuRefreshCw,
  LuPencil,
  LuThumbsUp,
  LuThumbsDown,
  LuVolume2,
  LuSquare,
} from "react-icons/lu";

interface Props {
  text: string;
  role: "user" | "alpha";
  /** Show Regenerate (only meaningful on the latest Alpha reply). */
  canRegenerate?: boolean;
  onRegenerate?: () => void;
  /** Edit & resend this user prompt. */
  onEdit?: () => void;
  /** Fire with the new vote value (or null when toggled off) — callers persist to backend. */
  onVote?: (vote: "up" | "down" | null) => void;
}

const BTN =
  "p-1 rounded text-[#71717a] hover:text-white hover:bg-white/5 transition-colors cursor-pointer";

export function MessageActions({ text, role, canRegenerate, onRegenerate, onEdit, onVote }: Props) {
  const [copied, setCopied] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const speakingRef = useRef(false);

  function copy() {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  }

  function readAloud() {
    const synth = window.speechSynthesis;
    if (!synth) return;
    if (speakingRef.current) {
      synth.cancel();
      return; // onend flips state off
    }
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.onend = () => {
      speakingRef.current = false;
      setSpeaking(false);
    };
    u.onerror = u.onend;
    speakingRef.current = true;
    setSpeaking(true);
    synth.speak(u);
  }

  // Stop this message's speech if it unmounts mid-read.
  useEffect(() => () => {
    if (speakingRef.current) window.speechSynthesis?.cancel();
  }, []);

  return (
    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
      <button className={BTN} onClick={copy} title={copied ? "Copied" : "Copy"} aria-label="Copy message">
        {copied ? <LuCheck size={14} className="text-[#3fb27f]" /> : <LuCopy size={14} />}
      </button>

      {role === "user" && onEdit && (
        <button className={BTN} onClick={onEdit} title="Edit & resend" aria-label="Edit and resend">
          <LuPencil size={14} />
        </button>
      )}

      {role === "alpha" && canRegenerate && onRegenerate && (
        <button className={BTN} onClick={onRegenerate} title="Regenerate" aria-label="Regenerate reply">
          <LuRefreshCw size={14} />
        </button>
      )}

      {role === "alpha" && (
        <>
          <button
            className={`${BTN} ${speaking ? "text-[#e6a23c]" : ""}`}
            onClick={readAloud}
            title={speaking ? "Stop" : "Read aloud"}
            aria-label={speaking ? "Stop reading" : "Read aloud"}
          >
            {speaking ? <LuSquare size={13} /> : <LuVolume2 size={14} />}
          </button>
          <button
            className={`${BTN} ${vote === "up" ? "text-[#3fb27f]" : ""}`}
            onClick={() => {
              const next = vote === "up" ? null : "up";
              setVote(next);
              onVote?.(next);
            }}
            title="Good reply"
            aria-label="Good reply"
            aria-pressed={vote === "up"}
          >
            <LuThumbsUp size={14} />
          </button>
          <button
            className={`${BTN} ${vote === "down" ? "text-[#e6a23c]" : ""}`}
            onClick={() => {
              const next = vote === "down" ? null : "down";
              setVote(next);
              onVote?.(next);
            }}
            title="Bad reply"
            aria-label="Bad reply"
            aria-pressed={vote === "down"}
          >
            <LuThumbsDown size={14} />
          </button>
        </>
      )}
    </div>
  );
}
