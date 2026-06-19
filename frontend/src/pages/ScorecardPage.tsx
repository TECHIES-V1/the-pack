// Scorecard — Lone Wolf vs The Pack (Doc 01/02, the benchmark). Shows the same task run two
// ways and scored side by side: the pack's whole reason to exist.
//
// NOTE: the engine's /benchmark is a stub today, so these numbers are representative of the
// design. Wire to a real benchmark run when it lands (Explicitly NEXT).

import { LuX } from "react-icons/lu";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

interface Row {
  label: string;
  lone: string;
  pack: string;
  packWins: boolean;
}

const ROWS: Row[] = [
  { label: "Sources found", lone: "2", pack: "9", packWins: true },
  { label: "Accuracy", lone: "Repeated the 5M claim", pack: "Flagged it unverified", packWins: true },
  { label: "Citations", lone: "0", pack: "3", packWins: true },
  { label: "Cost", lone: "$0.18", pack: "$0.56", packWins: false },
  { label: "Time", lone: "3m 30s", pack: "4m 30s", packWins: false },
];

export function ScorecardPage({ huntId }: { huntId: string }) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center font-sans">
      <div className="w-[min(560px,92vw)] bg-[#1A1A1A] border border-[#2a2a2a] rounded-2xl text-white overflow-hidden">
        <header className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a2a]">
          <h1 className="text-[16px] font-medium m-0">Lone Wolf vs The Pack</h1>
          <button className="text-[#a1a1aa] hover:text-white" onClick={() => goTo(`/artifact/${huntId}`)}>
            <LuX size={18} />
          </button>
        </header>

        <div className="px-6 py-2">
          <div className="grid grid-cols-[1.4fr_1fr_1fr] gap-px text-[13px]">
            <div className="py-3 text-[#71717a]" />
            <div className="py-3 text-[#a1a1aa] text-center">Lone Wolf</div>
            <div className="py-3 text-center font-medium flex items-center justify-center gap-1.5">
              <span className="text-[#e6a23c]">★</span> The Pack
            </div>
            {ROWS.map((r) => (
              <Cells key={r.label} row={r} />
            ))}
          </div>
        </div>

        <footer className="flex justify-end gap-2 px-6 py-4 border-t border-[#2a2a2a]">
          <button
            className="bg-transparent text-[#a1a1aa] border border-[#2a2a2a] rounded-lg px-4 py-2 text-[13px] cursor-pointer"
            onClick={() => goTo(`/artifact/${huntId}`)}
          >
            Cancel
          </button>
          <button className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium cursor-pointer border-none">
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
