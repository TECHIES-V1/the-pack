// Scorecard — Lone Wolf vs The Pack (Doc 01/02, the benchmark). Shows the same task run two
// ways and scored side by side: the pack's whole reason to exist. Real data from the engine's
// /benchmark run — if none exists yet, this triggers one and polls for the result.

import { useEffect, useState } from "react";
import { LuX } from "react-icons/lu";
import { api, type Scorecard } from "@/net/api";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function fmtCost(n: number): string {
  return `$${n.toFixed(2)}`;
}
function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return m ? `${m}m ${r}s` : `${r}s`;
}

interface Row {
  label: string;
  lone: string;
  pack: string;
  packWins: boolean;
}

function buildRows(c: Scorecard): Row[] {
  return [
    { label: "Quality", lone: c.lone_wolf.quality.toFixed(2), pack: c.pack.quality.toFixed(2), packWins: c.pack.quality >= c.lone_wolf.quality },
    { label: "Sources found", lone: String(c.lone_wolf.sources), pack: String(c.pack.sources), packWins: c.pack.sources >= c.lone_wolf.sources },
    { label: "Citations", lone: String(c.lone_wolf.citations), pack: String(c.pack.citations), packWins: c.pack.citations >= c.lone_wolf.citations },
    { label: "Cost", lone: fmtCost(c.lone_wolf.cost_usd), pack: fmtCost(c.pack.cost_usd), packWins: c.pack.cost_usd <= c.lone_wolf.cost_usd },
    { label: "Time", lone: fmtTime(c.lone_wolf.time_s), pack: fmtTime(c.pack.time_s), packWins: c.pack.time_s <= c.lone_wolf.time_s },
  ];
}

type Status = "loading" | "running" | "ready" | "error";

export function ScorecardPage({ huntId }: { huntId: string }) {
  const [card, setCard] = useState<Scorecard | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { scorecard } = await api.getScorecard(huntId);
        if (!cancelled) {
          setCard(scorecard);
          setStatus("ready");
        }
        return;
      } catch {
        // No scorecard yet — kick off a real benchmark and poll for it.
      }
      if (cancelled) return;
      setStatus("running");
      try {
        await api.benchmark(huntId);
      } catch {
        /* ignore — poll anyway */
      }
      for (let i = 0; i < 30 && !cancelled; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        try {
          const { scorecard } = await api.getScorecard(huntId);
          if (!cancelled) {
            setCard(scorecard);
            setStatus("ready");
          }
          return;
        } catch {
          /* not ready yet */
        }
      }
      if (!cancelled) setStatus("error");
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [huntId]);

  const rows = card ? buildRows(card) : [];

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center font-sans">
      <div className="w-[min(560px,92vw)] bg-[#1A1A1A] border border-[#2a2a2a] rounded-2xl text-white overflow-hidden">
        <header className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a2a]">
          <h1 className="text-[16px] font-medium m-0">Lone Wolf vs The Pack</h1>
          <button className="text-[#a1a1aa] hover:text-white" onClick={() => goTo(`/hunt/${huntId}`)}>
            <LuX size={18} />
          </button>
        </header>

        {status !== "ready" ? (
          <div className="px-6 py-12 text-center text-[13px] text-[#a1a1aa]">
            {status === "error"
              ? "Couldn't run the benchmark — make sure the engine is running and try again."
              : status === "running"
                ? "Running the lone wolf against the pack…"
                : "Loading the scorecard…"}
          </div>
        ) : (
          <div className="px-6 py-2">
            <div className="grid grid-cols-[1.4fr_1fr_1fr] gap-px text-[13px]">
              <div className="py-3 text-[#71717a]" />
              <div className="py-3 text-[#a1a1aa] text-center">Lone Wolf</div>
              <div className="py-3 text-center font-medium flex items-center justify-center gap-1.5">
                <span className="text-[#e6a23c]">★</span> The Pack
              </div>
              {rows.map((r) => (
                <Cells key={r.label} row={r} />
              ))}
            </div>
          </div>
        )}

        <footer className="flex justify-end gap-2 px-6 py-4 border-t border-[#2a2a2a]">
          <button
            className="bg-transparent text-[#a1a1aa] border border-[#2a2a2a] rounded-lg px-4 py-2 text-[13px] cursor-pointer"
            onClick={() => goTo(`/hunt/${huntId}`)}
          >
            Close
          </button>
          <button
            disabled={!card}
            className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium cursor-pointer border-none disabled:opacity-50"
            onClick={() => {
              const data = { hunt_id: huntId, scorecard: card };
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `scorecard-${huntId}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            Export
          </button>
        </footer>
      </div>
    </div>
  );
}

function Cells({ row }: { row: Row }) {
  return (
    <>
      <div className="py-3 border-t border-[#242424] text-[#d4d4d8]">{row.label}</div>
      <div className="py-3 border-t border-[#242424] text-center text-[#a1a1aa]">{row.lone}</div>
      <div className={`py-3 border-t border-[#242424] text-center ${row.packWins ? "text-[#3fb27f]" : "text-[#d4d4d8]"}`}>
        {row.pack}
      </div>
    </>
  );
}
