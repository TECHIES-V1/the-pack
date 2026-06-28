// Instincts Library (S — Doc 02) — a gallery of starter formations. Each card previews the pack that
// will range (FormationPreview) and what it brings back; picking one prompts for a topic and launches
// a hunt seeded with that formation. User-saved instincts sit alongside the defaults.

import { useEffect, useState } from "react";
import { LuArrowLeft } from "react-icons/lu";
import { FormationPreview } from "@/canvas/FormationPreview";
import { api, type Instinct, type StrategyName } from "@/net/api";
import type { TeamMember } from "@/events/reducer";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

// A full pack with N scouts — leads + the variable scouts + support, matching the engine's roster so
// the preview looks like what actually spawns.
const pack = (scouts: number): TeamMember[] => [
  { role: "alpha", count: 1 },
  { role: "beta", count: 1 },
  { role: "scout", count: scouts },
  { role: "tracker", count: 1 },
  { role: "sentinel", count: 1 },
  { role: "howler", count: 1 },
  { role: "elder", count: 1 },
];

interface Formation {
  key: string;
  label: string;
  brings: string;
  strategy: StrategyName;
  team: TeamMember[];
}

const FORMATIONS: Formation[] = [
  { key: "deep-research", label: "Deep Research", brings: "A thorough, multi-source briefing with citations.", strategy: "deep_dive", team: pack(5) },
  { key: "summarize", label: "Summarize & Extract", brings: "The key points and figures, pulled clean.", strategy: "orchestrate", team: pack(2) },
  { key: "web-page", label: "Build a Web Page", brings: "A drafted page (HTML) on your topic.", strategy: "orchestrate", team: pack(3) },
  { key: "document", label: "Draft a Document", brings: "A clean written document (PDF / DOCX).", strategy: "orchestrate", team: pack(3) },
  { key: "analyze-data", label: "Analyze Data", brings: "Findings plus a data view from your sources.", strategy: "critique", team: pack(3) },
  { key: "deck", label: "Make a Deck", brings: "A slide-shaped outline on your topic.", strategy: "orchestrate", team: pack(3) },
  { key: "market-scan", label: "Competitor / Market Scan", brings: "Players, positioning, and the landscape.", strategy: "critique", team: pack(4) },
];

export function LibraryPage() {
  const [saved, setSaved] = useState<Instinct[]>([]);

  useEffect(() => {
    api.listInstincts().then((r) => setSaved(r.instincts)).catch(() => {});
  }, []);

  function launch(team: TeamMember[], strategy: StrategyName) {
    const topic = window.prompt("What should this pack hunt down?")?.trim();
    if (!topic) return;
    const seed = team.map((m) => ({ role: m.role, count: m.count }));
    api
      .createHunt({ input: topic, source: "typed", strategy, team: seed })
      .then(({ hunt_id }) => goTo(`/hunt/${hunt_id}/plan`))
      .catch(() => {});
  }

  function launchInstinct(id: string) {
    api
      .createHunt({ instinct_id: id, source: "typed" })
      .then(({ hunt_id }) => goTo(`/hunt/${hunt_id}/plan`))
      .catch(() => {});
  }

  return (
    <div className="min-h-screen bg-door-bg text-white font-sans">
      <header className="flex items-center gap-3 px-6 py-4 border-b border-[#2a2a2a]">
        <button
          onClick={() => goTo("/")}
          className="p-2 text-[#a1a1aa] hover:text-white bg-transparent border-none cursor-pointer"
          title="Home"
        >
          <LuArrowLeft size={18} />
        </button>
        <h1 className="text-[18px] font-medium m-0">Instincts Library</h1>
        <span className="text-[13px] text-[#71717a]">Pick a formation to start a hunt</span>
      </header>

      <div className="max-w-[1100px] mx-auto px-6 py-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FORMATIONS.map((f) => (
            <button
              key={f.key}
              onClick={() => launch(f.team, f.strategy)}
              className="text-left bg-[#141414] border border-[#2a2a2a] rounded-2xl p-3 hover:border-[#404040] cursor-pointer flex flex-col gap-2"
            >
              <div className="rounded-xl overflow-hidden bg-[#0F0F0F] border border-[#222]">
                <FormationPreview team={f.team} height={150} />
              </div>
              <div className="px-1">
                <div className="text-[14px] font-medium">{f.label}</div>
                <div className="text-[12px] text-[#a1a1aa] mt-0.5">{f.brings}</div>
              </div>
            </button>
          ))}
        </div>

        {saved.length > 0 && (
          <>
            <h2 className="text-[14px] font-medium mt-10 mb-3">Your saved instincts</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {saved.map((i) => {
                const team = (i.spec?.team as TeamMember[] | undefined) ?? null;
                return (
                  <button
                    key={i.instinct_id}
                    onClick={() => launchInstinct(i.instinct_id)}
                    className="text-left bg-[#141414] border border-[#2a2a2a] rounded-2xl p-3 hover:border-[#404040] cursor-pointer flex flex-col gap-2"
                  >
                    {team && (
                      <div className="rounded-xl overflow-hidden bg-[#0F0F0F] border border-[#222]">
                        <FormationPreview team={team} height={130} />
                      </div>
                    )}
                    <div className="px-1 text-[14px] font-medium truncate">{i.label}</div>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
