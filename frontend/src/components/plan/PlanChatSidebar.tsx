// Chat session (right rail of the hunt screen, Doc 02/03). Renders ONLY from the hunt store:
// Alpha's narration, the spend meter, the Hunt Summary (Start Hunt = approve), the Hold card
// (Submit = resolve), and the final artifact card. Commands go to the engine; truth comes back
// on the stream.

import { useState } from "react";
import { OneBox } from "@/components/composer/OneBox";
import { api } from "@/net/api";
import { useHuntStore } from "@/store/huntStore";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const PANEL = "bg-[#1A1A1A] border border-[#2a2a2a] rounded-[12px]";

export function PlanChatSidebar({ huntId }: { huntId: string }) {
  const view = useHuntStore((s) => s.view);
  const [asks, setAsks] = useState<string[]>([]);
  const [boundary, setBoundary] = useState(1.0);
  const [pick, setPick] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const hold = view.openHold;
  const resolution = pick ?? hold?.recommended ?? hold?.options[0] ?? "";

  async function startHunt() {
    setBusy(true);
    try {
      await api.approvePlan(huntId, { mode: "on_signal", boundary_usd: boundary });
    } finally {
      setBusy(false);
    }
  }

  async function resolveHold() {
    if (!hold) return;
    setBusy(true);
    try {
      await api.resolveHold(huntId, hold.holdId, { resolution });
      setPick(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="w-[340px] shrink-0 flex flex-col bg-[#1A1A1A] text-white overflow-hidden m-2 rounded-[12px] border border-[#2a2a2a]">
      <div className="px-5 pt-5 pb-4 border-b border-[#2a2a2a] flex items-center justify-between">
        <h2 className="text-[14px] font-medium m-0 leading-none">Chat session</h2>
        {view.boundary.boundaryUsd > 0 && (
          <span className="text-[11px] text-[#a1a1aa]">
            ${view.boundary.cumulativeUsd.toFixed(2)} spent · {view.boundary.pct.toFixed(0)}%
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 scrollbar-subtle">
        {/* Alpha's narration */}
        {view.feed.map((line) => (
          <div key={line.seq} className="text-[13px] leading-relaxed text-[#d4d4d8]">
            <span className="text-[#71717a] mr-1">·</span>
            {line.text}
          </div>
        ))}

        {/* User asks (local echo — no chat backend yet) */}
        {asks.map((m, i) => (
          <div key={`ask-${i}`} className="bg-[#242424] rounded-xl p-3 text-[13px] text-[#d4d4d8] self-end max-w-[90%]">
            {m}
          </div>
        ))}

        {/* Hunt Summary — the approve gate */}
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
              onClick={startHunt}
              disabled={busy}
              className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium hover:bg-white/90 disabled:opacity-60 cursor-pointer border-none"
            >
              Start Hunt →
            </button>
          </div>
        )}

        {/* Hold — human decision */}
        {hold && (
          <div className={`${PANEL} p-4 flex flex-col gap-3`}>
            <h3 className="text-[13px] font-medium m-0">{hold.question}</h3>
            <div className="flex flex-col gap-2">
              {hold.options.map((opt) => (
                <label key={opt} className="flex items-center gap-2 text-[12px] text-[#d4d4d8] cursor-pointer">
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
              onClick={resolveHold}
              disabled={busy}
              className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium hover:bg-white/90 disabled:opacity-60 cursor-pointer border-none self-end"
            >
              Submit
            </button>
          </div>
        )}

        {/* Final artifact */}
        {view.finalArtifactId && (
          <div className={`${PANEL} p-4 flex flex-col gap-3`}>
            <div className="flex items-center gap-2 text-[13px]">
              <span className="text-[#e03a2f]">▌</span> Verification claim
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => goTo(`/artifact/${huntId}`)}
                className="bg-white text-black rounded-lg px-3 py-1.5 text-[12px] font-medium cursor-pointer border-none"
              >
                Open
              </button>
              <button className="bg-transparent text-[#a1a1aa] border border-[#2a2a2a] rounded-lg px-3 py-1.5 text-[12px] cursor-pointer">
                Save instinct
              </button>
            </div>
          </div>
        )}

        {/* Failed */}
        {view.state === "failed" && (
          <div className="text-[13px] text-[#e03a2f]">The pack couldn't finish this one.</div>
        )}
      </div>

      <div className="p-4 pt-2">
        <OneBox
          placeholder="Ask Alpha anything about this plan..."
          onSubmit={(payload) => setAsks((prev) => [...prev, payload.text])}
        />
      </div>
    </aside>
  );
}
