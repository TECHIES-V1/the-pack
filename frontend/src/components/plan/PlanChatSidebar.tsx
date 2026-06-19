// Chat session (right rail). Renders from the hunt store: the task, Alpha's narration, the
// spend meter, the Hunt Summary (Start Hunt = approve), the Hold card (Submit = resolve), a Stop
// control while running, and a real "Ask Alpha" box. Commands go to the engine; truth returns
// on the stream.

import { useEffect, useState } from "react";
import { AlphaAvatar } from "@/components/chat/AlphaAvatar";
import { TypeOut } from "@/components/chat/TypeOut";
import { OneBox } from "@/components/composer/OneBox";
import { api } from "@/net/api";
import { useHuntStore } from "@/store/huntStore";
import { useChatStore } from "@/store/chatStore";

const PANEL = "bg-[#1A1A1A] border border-[#2a2a2a] rounded-[12px]";
const RUNNING = new Set(["hunting", "holding", "standoff", "finishing"]);

export function PlanChatSidebar({ huntId }: { huntId: string }) {
  const view = useHuntStore((s) => s.view);
  const { turns, pending, addUser, addAlpha, setPending } = useChatStore();
  const [task, setTask] = useState("");
  const [boundary, setBoundary] = useState(1.0);
  const [pick, setPick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getHunt(huntId).then((s) => setTask(s.task)).catch(() => {});
  }, [huntId]);

  const hold = view.openHold;
  const resolution = pick ?? hold?.recommended ?? hold?.options[0] ?? "";

  async function guard(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  }

  async function askAlpha(question: string) {
    addUser(question);
    setPending(true);
    try {
      const { reply } = await api.ask(huntId, question);
      addAlpha(reply);
    } catch {
      addAlpha("I couldn't reach you just now — try me again.");
    } finally {
      setPending(false);
    }
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
              className="text-[11px] text-[#e03a2f] hover:text-[#ff6b5e] bg-transparent border-none cursor-pointer p-0"
            >
              Stop
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 scrollbar-subtle">
        {/* The conversation carried over from the Door (falls back to the task if opened cold) */}
        {turns.length > 0
          ? turns.map((t, i) =>
              t.role === "user" ? (
                <div
                  key={i}
                  className="bg-[#242424] rounded-xl p-3 text-[13px] text-[#d4d4d8] self-end max-w-[90%]"
                >
                  {t.text}
                </div>
              ) : (
                <div key={i} className="flex gap-2 items-start">
                  <AlphaAvatar size={22} />
                  <p className="text-[13px] leading-relaxed text-[#d4d4d8] m-0 pt-px">
                    <TypeOut text={t.text} />
                  </p>
                </div>
              ),
            )
          : task && (
              <div className="bg-[#242424] rounded-xl p-3 text-[13px] text-[#d4d4d8] self-end max-w-[90%]">
                {task}
              </div>
            )}

        {pending && (
          <div className="flex gap-2 items-center">
            <AlphaAvatar size={22} />
            <span className="text-[13px] text-[#71717a] italic">Alpha is thinking…</span>
          </div>
        )}

        {view.feed.map((line) => (
          <div
            key={line.seq}
            className="flex gap-2.5 items-start py-2 border-b border-[#202020] last:border-0"
          >
            <span className="mt-[7px] w-1.5 h-1.5 rounded-full bg-[#e6a23c]/70 shrink-0" />
            <p className="text-[13px] leading-relaxed text-[#d4d4d8] m-0">{line.text}</p>
          </div>
        ))}

        {view.state === "plan_ready" && view.plan && (
          <div className={`${PANEL} p-4 flex flex-col gap-3`}>
            <h3 className="text-[13px] font-medium m-0">Hunt Summary</h3>
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
              onClick={() => guard(() => api.approvePlan(huntId, { mode: "on_signal", boundary_usd: boundary }))}
              disabled={busy}
              className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium hover:bg-white/90 disabled:opacity-60 cursor-pointer border-none"
            >
              Send the pack →
            </button>
          </div>
        )}

        {hold && (
          <div className={`${PANEL} p-4 flex flex-col gap-3`}>
            <h3 className="text-[13px] font-medium m-0">{hold.question}</h3>
            <div className="flex flex-col gap-2">
              {hold.options.map((opt) => (
                <label key={opt} className="flex items-center gap-2 text-[12px] text-[#d4d4d8] cursor-pointer">
                  <input type="radio" name="hold" checked={resolution === opt} onChange={() => setPick(opt)} />
                  {opt}
                  {opt === hold.recommended && <span className="text-[#71717a]">(recommended)</span>}
                </label>
              ))}
            </div>
            <button
              onClick={() => guard(() => api.resolveHold(huntId, hold.holdId, { resolution }).then(() => setPick(null)))}
              disabled={busy}
              className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium hover:bg-white/90 disabled:opacity-60 cursor-pointer border-none self-end"
            >
              Submit
            </button>
          </div>
        )}

        {view.state === "failed" && (
          <div className="text-[13px] text-[#e03a2f]">The pack couldn't finish this one.</div>
        )}
      </div>

      <div className="p-4 pt-2">
        <OneBox
          placeholder="Ask Alpha anything about this plan..."
          onSubmit={(payload) => askAlpha(payload.text)}
        />
      </div>
    </aside>
  );
}
