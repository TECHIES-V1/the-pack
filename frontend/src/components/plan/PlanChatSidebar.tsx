// Chat session (right rail) — Phase 3.
//
// This rail is now CONVERSATION + the human gates, nothing else. The live activity narrative
// moved to the Territory's TraceRail, so the chat stops being feed-soup. The gates (Start Hunt,
// resolve a Hold) are PINNED below the header so their buttons never scroll away. "Ask Alpha"
// carries the whole conversation, so Alpha remembers the thread. Commands go to the engine;
// truth returns on the stream.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { AlphaAvatar } from "@/components/chat/AlphaAvatar";
import { MarkdownReply } from "@/components/chat/MarkdownReply";
import { MessageActions } from "@/components/chat/MessageActions";
import { ThinkingIndicator } from "@/components/chat/ThinkingIndicator";
import { OneBox } from "@/components/composer/OneBox";
import { api, streamSSE, ApiError, type IntakeTurn } from "@/net/api";
import { useHuntStore } from "@/store/huntStore";
import { useChatStore } from "@/store/chatStore";
import { withCustomInstructions } from "@/store/settingsStore";

const PANEL = "bg-[#1A1A1A] border border-[#2a2a2a] rounded-[12px]";
const RUNNING = new Set(["hunting", "holding", "standoff", "finishing"]);

const ERROR_MESSAGES: Record<string, string> = {
  engine_down: "The engine isn't running — start it with `uvicorn app.main:app`.",
  rate_limit: "Alpha is rate-limited — give it ~30 seconds and try again.",
  timeout: "That took too long — try again.",
  content_filter: "That topic was filtered — try rephrasing.",
  context_exceeded: "This hunt's context is full — start a new one.",
  unknown: "Couldn't reach Alpha — check the connection.",
};

const STRATEGY_LABEL: Record<string, string> = {
  orchestrate: "Dynamic orchestrator",
  deep_dive: "Iterative deep-research",
  critique: "Plan-execute-critique",
};

// How tightly the Packmaster holds the leash — sent to the engine at approval (it honors all three).
type Autonomy = "on_command" | "on_signal" | "wild";
const MODES: { value: Autonomy; label: string; blurb: string }[] = [
  { value: "on_command", label: "On Command", blurb: "Alpha pauses at forks and checks in before he writes the brief." },
  { value: "on_signal", label: "On Signal", blurb: "Alpha runs, but pauses when the pack genuinely disagrees." },
  { value: "wild", label: "On Wild", blurb: "Alpha makes the calls himself and brings back the result." },
];

export function PlanChatSidebar({ huntId }: { huntId: string }) {
  const view = useHuntStore((s) => s.view);
  const { turns, pending, addUser, startAlpha, addAlphaToken, commitAlpha, setPending, dropLastAlpha, truncateFrom, setAbortFn } =
    useChatStore();
  const [task, setTask] = useState("");
  const [boundary, setBoundary] = useState(1.0);
  const [mode, setMode] = useState<Autonomy>("on_signal");
  // Edited research angles before launch (null = untouched → no edits sent).
  const [editedQueries, setEditedQueries] = useState<string[] | null>(null);
  const [pick, setPick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [prefill, setPrefill] = useState<string | undefined>();
  // While the pack runs, the composer can either ask Alpha (side-chat) or feed the live hunt.
  const [target, setTarget] = useState<"ask" | "feed">("ask");
  const prevStateRef = useRef(view.state);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  let lastAlpha = -1;
  turns.forEach((t, i) => {
    if (t.role === "alpha") lastAlpha = i;
  });

  useEffect(() => {
    api.getHunt(huntId).then((s) => setTask(s.task)).catch(() => {});
    // If we arrived without the conversation in memory (Den / refresh / another device), hydrate
    // it from the hunt's saved messages.
    if (useChatStore.getState().turns.length === 0) {
      api
        .getMessages(huntId)
        .then((r) => {
          if (r.messages.length) useChatStore.getState().hydrate(r.messages);
        })
        .catch(() => {});
    }
  }, [huntId]);

  // Track whether the user is at the bottom (so we never yank them down while they read history).
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      stickRef.current = el.scrollHeight - (el.scrollTop + el.clientHeight) < 120;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Pin to the newest line only when already at the bottom; never the document root.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [turns, pending]);

  const hold = view.openHold;
  const resolution = pick ?? hold?.recommended ?? hold?.options[0] ?? "";
  const halted = view.state === "halted_boundary";

  // When plan_ready first arrives, inject a conversational plan summary from Alpha.
  const { addAlpha: _addAlpha } = useChatStore.getState();
  useEffect(() => {
    if (prevStateRef.current !== "plan_ready" && view.state === "plan_ready" && view.plan) {
      const { est_cost, est_time, pattern, steps, strategy } = view.plan;
      const label = STRATEGY_LABEL[strategy ?? ""] ?? pattern;
      const n = steps?.length ?? 0;
      const msg = `Beta's ready — ${n} step${n !== 1 ? "s" : ""}, ${label} pattern. Estimated cost $${est_cost.toFixed(2)}, ~${Math.round(est_time / 60)} min. I've set a $${boundary.toFixed(2)} spending limit. Ready to go?`;
      useChatStore.getState().addAlpha(msg);
    }
    prevStateRef.current = view.state;
  }, [view.state]);

  async function guard(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  }

  // Carry the whole thread so Alpha remembers what we've been talking about.
  // Streams tokens live into an open Alpha bubble — first token appears in <500ms.
  async function runAsk() {
    const history: IntakeTurn[] = withCustomInstructions(
      useChatStore.getState().turns.map((t) => ({
        role: t.role === "alpha" ? "assistant" : "user",
        content: t.text,
      })),
    );
    setAskError(null);
    setPending(true);
    startAlpha(); // open empty bubble immediately
    const ctrl = new AbortController();
    setAbortFn(() => ctrl.abort());
    try {
      let streamError: string | null = null;
      for await (const event of streamSSE(`/hunts/${huntId}/ask/stream`, { messages: history }, ctrl.signal)) {
        if (event.type === "error") {
          streamError = ERROR_MESSAGES[(event.kind as string) ?? "unknown"] ?? ERROR_MESSAGES.unknown;
          break;
        }
        if (event.type === "token") addAlphaToken(event.text as string);
      }
      if (streamError) {
        dropLastAlpha();
        setAskError(streamError);
      } else {
        commitAlpha(); // strip dashes + persist to backend
      }
    } catch (err) {
      dropLastAlpha(); // remove the partial bubble
      setAskError(err instanceof ApiError ? ERROR_MESSAGES[err.kind] : ERROR_MESSAGES.unknown);
    } finally {
      setAbortFn(null);
      setPending(false);
    }
  }

  async function askAlpha(question: string) {
    addUser(question);
    await runAsk();
  }

  // Feed the running hunt: the engine absorbs it before the next step (emits input_added).
  function addToHunt(text: string) {
    const t = text.trim();
    if (!t) return;
    addUser(`📌 Added to the hunt: ${t}`);
    api.addInput(huntId, t).catch(() => {});
  }

  // A file dropped on the rail is parsed and folded into the hunt as source material.
  async function attachFileToHunt(file: File) {
    const t = file.type;
    if (t.startsWith("video/")) {
      addUser("📎 I can't read video yet — try an image, PDF, doc, spreadsheet, or audio file.");
      return;
    }
    addUser(`📎 Reading ${file.name} into the hunt…`);
    try {
      const isAudio = t.startsWith("audio/");
      const parsed = isAudio ? await api.transcribe(file) : await api.parse(file);
      const text = (parsed.text || "").trim();
      if (!text) {
        addUser(`I couldn't pull any text out of ${file.name}.`);
        return;
      }
      await api.addInput(huntId, `Source material from ${file.name}:\n\n${text}`.slice(0, 8000));
    } catch {
      addUser("I couldn't read that file just now — try again, or tell me what's in it.");
    }
  }

  async function regenerate() {
    dropLastAlpha();
    await runAsk();
  }

  function editTurn(index: number) {
    const t = useChatStore.getState().turns[index];
    if (!t) return;
    setPrefill(t.text);
    truncateFrom(index);
  }

  return (
    <aside className="w-[340px] shrink-0 flex flex-col bg-[#1A1A1A] text-white overflow-hidden m-2 rounded-[12px] border border-[#2a2a2a]">
      <div className="px-5 pt-5 pb-4 border-b border-[#2a2a2a] flex items-center justify-between">
        <h2 className="text-[14px] font-medium m-0 leading-none">Chat session</h2>
        <div className="flex items-center gap-3">
          {view.boundary.cumulativeUsd > 0 && (
            <span className="text-[11px] text-[#a1a1aa]">
              ${view.boundary.cumulativeUsd.toFixed(2)} · {view.boundary.pct.toFixed(0)}%
            </span>
          )}
          {RUNNING.has(view.state) && (
            <button
              onClick={() => guard(() => api.stop(huntId))}
              className="text-[12px] text-[#ff6b5e] border border-[#e03a2f]/50 rounded-md px-2.5 py-1 hover:bg-[#e03a2f]/15 bg-transparent cursor-pointer leading-none"
            >
              Stop
            </button>
          )}
        </div>
      </div>

      {/* assertive: hold gates demand immediate attention from screen readers */}
      <div aria-live="assertive" aria-atomic="true">
        {hold && (
          <div className="shrink-0 px-4 pt-3">
            <div className={`${PANEL} p-4 flex flex-col gap-3`}>
              <h3 className="text-[13px] font-medium m-0">{hold.question}</h3>
              <div className="flex flex-col gap-2">
                {hold.options.map((opt) => (
                  <label
                    key={opt}
                    className="flex items-center gap-2 text-[12px] text-[#d4d4d8] cursor-pointer"
                  >
                    <input
                      type="radio"
                      name="hold"
                      checked={resolution === opt}
                      onChange={() => setPick(opt)}
                    />
                    {opt}
                    {opt === hold.recommended && <span className="text-[#71717a]">(recommended)</span>}
                  </label>
                ))}
              </div>
              <button
                onClick={() =>
                  guard(() =>
                    api.resolveHold(huntId, hold.holdId, { resolution }).then(() => setPick(null)),
                  )
                }
                disabled={busy}
                className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium hover:bg-white/90 disabled:opacity-60 cursor-pointer border-none self-end"
              >
                Submit
              </button>
            </div>
          </div>
        )}
      </div>

      {halted && (
        <div className="shrink-0 px-4 pt-3">
          <div className={`${PANEL} p-4 flex flex-col gap-3`}>
            <h3 className="text-[13px] font-medium m-0 text-[#e6a23c]">Boundary reached</h3>
            <p className="text-[12px] text-[#a1a1aa] m-0">
              The pack paused before spending past your cap (${view.boundary.cumulativeUsd.toFixed(2)} so
              far). Raise it to let the hunt finish.
            </p>
            <label className="text-[12px] text-[#a1a1aa] flex items-center gap-2">
              New boundary $
              <input
                type="number"
                step="0.25"
                min={view.boundary.cumulativeUsd}
                value={boundary}
                onChange={(e) => setBoundary(Number(e.target.value))}
                className="w-20 bg-[#0F0F0F] border border-[#2a2a2a] rounded-md px-2 py-1 text-white"
              />
            </label>
            <div className="flex gap-2 self-end">
              <button
                onClick={() => guard(() => api.stop(huntId))}
                disabled={busy}
                className="bg-transparent text-[#a1a1aa] border border-[#2a2a2a] rounded-lg px-3 py-2 text-[13px] cursor-pointer hover:text-white disabled:opacity-60"
              >
                Stop here
              </button>
              <button
                onClick={() =>
                  guard(() => api.resume(huntId, Math.max(boundary, view.boundary.cumulativeUsd + 0.25)))
                }
                disabled={busy}
                className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium hover:bg-white/90 disabled:opacity-60 cursor-pointer border-none"
              >
                Raise & resume →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Conversation only (the activity feed lives on the canvas TraceRail) ---------- */}
      <div
        ref={scrollRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 scrollbar-subtle"
      >
        {turns.length > 0
          ? turns.map((t, i) =>
              t.role === "user" ? (
                <div key={i} className="group flex flex-col items-end gap-1 self-end max-w-[90%]">
                  <div className="bg-[#242424] rounded-xl p-3 text-[13px] text-[#d4d4d8]">
                    {t.text}
                  </div>
                  <MessageActions text={t.text} role="user" onEdit={() => editTurn(i)} />
                </div>
              ) : (
                <div key={i} className="group flex gap-2 items-start">
                  <AlphaAvatar size={22} />
                  <div className="flex flex-col gap-1 min-w-0">
                    <div className="text-[13px] leading-relaxed text-[#d4d4d8] pt-px">
                      <MarkdownReply text={t.text} />
                    </div>
                    <MessageActions
                      text={t.text}
                      role="alpha"
                      canRegenerate={i === lastAlpha}
                      onRegenerate={regenerate}
                      onVote={(vote) => vote && api.submitFeedback(huntId, i, vote).catch(() => {})}
                    />
                  </div>
                </div>
              ),
            )
          : task && (
              <div className="bg-[#242424] rounded-xl p-3 text-[13px] text-[#d4d4d8] self-end max-w-[90%]">
                {task}
              </div>
            )}

        {pending && <ThinkingIndicator size={22} />}

        {askError && (
          <div className="flex items-center gap-2.5">
            <span className="text-[12px] text-[#e6a23c]">{askError}</span>
            <button
              onClick={() => runAsk()}
              className="rounded-md border border-[#2a2a2a] text-[#d4d4d8] hover:text-white px-2.5 py-1 text-[12px] cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {view.state === "failed" && (
          <div className="text-[13px] text-[#e03a2f]">The pack couldn't finish this one.</div>
        )}
      </div>

      <div className="p-4 pt-2">
        {RUNNING.has(view.state) && (
          <div className="flex rounded-lg bg-[#0F0F0F] border border-[#2a2a2a] p-0.5 mb-2">
            {([
              ["ask", "Ask Alpha"],
              ["feed", "Add to the hunt"],
            ] as const).map(([val, label]) => (
              <button
                key={val}
                onClick={() => setTarget(val)}
                aria-pressed={target === val}
                className={`flex-1 rounded-md px-2 py-1 text-[11.5px] cursor-pointer border-none transition-colors ${
                  target === val ? "bg-[#2e2e2e] text-white" : "bg-transparent text-[#a1a1aa] hover:text-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* Plan-ready gate — an unmistakable launch card (leash + budget + Send), pinned above the
            composer so it never hides when you type. */}
        {view.state === "plan_ready" && (
          <div className={`${PANEL} p-3 mb-2 flex flex-col gap-2.5`}>
            <div className="flex flex-col gap-1.5">
              <span className="text-[12px] text-[#a1a1aa]">How much leash?</span>
              <div className="flex rounded-lg bg-[#0F0F0F] border border-[#2a2a2a] p-0.5">
                {MODES.map((m) => (
                  <button
                    key={m.value}
                    onClick={() => setMode(m.value)}
                    aria-pressed={mode === m.value}
                    className={`flex-1 rounded-md px-2 py-1 text-[11px] cursor-pointer border-none transition-colors ${
                      mode === m.value ? "bg-[#2e2e2e] text-white" : "bg-transparent text-[#a1a1aa] hover:text-white"
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
              <span className="text-[11px] text-[#71717a]">{MODES.find((m) => m.value === mode)?.blurb}</span>
            </div>
            {view.plan?.queries && view.plan.queries.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-[12px] text-[#a1a1aa]">Angles the pack will chase — edit any</span>
                {(editedQueries ?? view.plan.queries).map((q, i) => (
                  <input
                    key={i}
                    value={q}
                    onChange={(e) => {
                      const base = editedQueries ?? view.plan!.queries!;
                      const next = [...base];
                      next[i] = e.target.value;
                      setEditedQueries(next);
                    }}
                    className="bg-[#0F0F0F] border border-[#2a2a2a] rounded-md px-2 py-1 text-[12px] text-white"
                  />
                ))}
              </div>
            )}
            <label className="flex items-center gap-2 text-[12px] text-[#a1a1aa]">
              Budget $
              <input
                type="number"
                step="0.25"
                min="0.25"
                value={boundary}
                onChange={(e) => setBoundary(Number(e.target.value))}
                className="w-20 bg-[#0F0F0F] border border-[#2a2a2a] rounded-md px-2 py-1 text-white"
              />
            </label>
            <button
              onClick={() =>
                guard(() => {
                  const edits =
                    editedQueries
                      ? { queries: editedQueries.map((s) => s.trim()).filter(Boolean) }
                      : undefined;
                  return api.approvePlan(huntId, { mode, boundary_usd: boundary, edits });
                })
              }
              disabled={busy}
              className="bg-[#3fb27f] text-white rounded-lg px-4 py-2 text-[13px] font-medium hover:bg-[#3fb27f]/90 disabled:opacity-70 cursor-pointer border-none"
            >
              {busy ? "Sending the pack…" : "Send the pack →"}
            </button>
          </div>
        )}

        <OneBox
          placeholder={
            view.state === "plan_ready"
              ? "Ask about the plan, or tweak it…"
              : target === "feed" && RUNNING.has(view.state)
              ? "Add a source or note for the pack…"
              : "Ask Alpha anything…"
          }
          prefill={prefill}
          onFilesAdded={(files) => files[0] && attachFileToHunt(files[0])}
          onSubmit={(payload) =>
            target === "feed" && RUNNING.has(view.state)
              ? addToHunt(payload.text)
              : askAlpha(payload.text)
          }
        />
        <p className="text-[10.5px] text-[#52525b] text-center mt-1.5">
          {target === "feed" && RUNNING.has(view.state)
            ? "The pack folds this in before its next step."
            : "Alpha can make mistakes. Check anything important."}
        </p>
      </div>
    </aside>
  );
}
