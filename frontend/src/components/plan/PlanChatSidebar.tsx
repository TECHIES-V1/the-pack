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
import { api, streamSSE, type IntakeTurn } from "@/net/api";
import { useHuntStore } from "@/store/huntStore";
import { useChatStore } from "@/store/chatStore";
import { withCustomInstructions } from "@/store/settingsStore";

const PANEL = "bg-[#1A1A1A] border border-[#2a2a2a] rounded-[12px]";
const RUNNING = new Set(["hunting", "holding", "standoff", "finishing"]);

const STRATEGY_LABEL: Record<string, string> = {
  orchestrate: "Dynamic orchestrator",
  deep_dive: "Iterative deep-research",
  critique: "Plan-execute-critique",
};

export function PlanChatSidebar({ huntId }: { huntId: string }) {
  const view = useHuntStore((s) => s.view);
  const { turns, pending, addUser, startAlpha, addAlphaToken, commitAlpha, setPending, dropLastAlpha, truncateFrom } =
    useChatStore();
  const [task, setTask] = useState("");
  const [boundary, setBoundary] = useState(1.0);
  const [pick, setPick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [askError, setAskError] = useState(false);
  const [prefill, setPrefill] = useState<string | undefined>();
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
  const showPlan = view.state === "plan_ready" && view.plan;
  const halted = view.state === "halted_boundary";

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
    setAskError(false);
    setPending(true);
    startAlpha(); // open empty bubble immediately
    try {
      for await (const event of streamSSE(`/hunts/${huntId}/ask/stream`, { messages: history })) {
        if (event.type === "token") addAlphaToken(event.text as string);
      }
      commitAlpha(); // strip dashes + persist to backend
    } catch {
      dropLastAlpha(); // remove the partial bubble
      setAskError(true);
    } finally {
      setPending(false);
    }
  }

  async function askAlpha(question: string) {
    addUser(question);
    await runAsk();
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

      {/* ---- Pinned gates: never scroll away ---------------------------------------------- */}
      {showPlan && view.plan && (
        <div className="shrink-0 px-4 pt-3">
          <div className={`${PANEL} p-4 flex flex-col gap-3`}>
            <div className="flex items-center justify-between">
              <h3 className="text-[13px] font-medium m-0">Hunt Summary</h3>
              {view.plan.strategy && (
                <span className="text-[10.5px] text-[#a1a1aa] bg-[#0F0F0F] border border-[#2a2a2a] rounded-full px-2 py-0.5">
                  {STRATEGY_LABEL[view.plan.strategy] ?? view.plan.strategy}
                </span>
              )}
            </div>
            <ul className="text-[12px] text-[#a1a1aa] flex flex-col gap-1 m-0 p-0 list-none">
              <li>Estimated time · {Math.round(view.plan.est_time / 60)} min</li>
              <li>Estimated cost · ${view.plan.est_cost.toFixed(2)}</li>
              <li>Pattern · {view.plan.pattern}</li>
            </ul>
            <label className="text-[12px] text-[#a1a1aa] flex items-center gap-2">
              Boundary $
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
                guard(() => api.approvePlan(huntId, { mode: "on_signal", boundary_usd: boundary }))
              }
              disabled={busy}
              className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium hover:bg-white/90 disabled:opacity-70 cursor-pointer border-none"
            >
              {busy ? "Sending the pack…" : "Send the pack →"}
            </button>
          </div>
        </div>
      )}

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
            <span className="text-[12px] text-[#e6a23c]">Couldn't reach Alpha.</span>
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
        <OneBox
          placeholder="Ask Alpha anything…"
          prefill={prefill}
          onSubmit={(payload) => askAlpha(payload.text)}
        />
        <p className="text-[10.5px] text-[#52525b] text-center mt-1.5">
          Alpha can make mistakes. Check anything important.
        </p>
      </div>
    </aside>
  );
}
