// Formation Edit Panel (v2) — shape the team Alpha proposed before launch. Per-role count steppers
// + per-wolf budgets, a live node-map preview, and a Shadow Hunt cost estimate. Optional depth — the
// one-tap Send still works untouched (this just stages a team the launch sends as edits.team).
//
// Per the UI guide, Scout *position* is never exposed (the AI places them; dagre lays them out) — only
// counts and budgets are editable. Alpha + Beta always lead and aren't editable.

import { useEffect, useState } from "react";
import { FormationPreview } from "@/canvas/FormationPreview";
import { api, type RehearseResult } from "@/net/api";
import { useFormationStore } from "@/store/formationStore";
import type { PlanView, TeamMember } from "@/events/reducer";

const LEADS = new Set(["alpha", "beta"]);
const LIMITS: Record<string, [number, number]> = {
  scout: [1, 5],
  tracker: [0, 2],
  sentinel: [0, 2],
  howler: [0, 2],
  elder: [0, 2],
};

export function FormationEditPanel({ huntId, plan }: { huntId: string; plan: PlanView }) {
  const { team, setTeam } = useFormationStore();
  const [rehearsal, setRehearsal] = useState<RehearseResult | null>(null);
  const [busy, setBusy] = useState(false);

  // Seed the staging team from the proposed plan once it arrives.
  useEffect(() => {
    if (!team && plan.team?.length) setTeam(plan.team.map((m) => ({ ...m })));
  }, [plan.team, team, setTeam]);

  const current = team ?? plan.team ?? [];
  if (!current.length) return null;

  function update(next: TeamMember[]) {
    setTeam(next);
    setRehearsal(null); // an edit invalidates the prior estimate
  }
  function bump(role: string, delta: number) {
    const [lo, hi] = LIMITS[role] ?? [0, 3];
    update(
      current.map((m) =>
        m.role === role ? { ...m, count: Math.max(lo, Math.min(hi, (m.count ?? 1) + delta)) } : m,
      ),
    );
  }
  function setBudget(role: string, value: number) {
    update(current.map((m) => (m.role === role ? { ...m, budget_usd: value } : m)));
  }

  async function shadowHunt() {
    setBusy(true);
    try {
      setRehearsal(await api.rehearse(huntId, current, plan.strategy));
    } catch {
      setRehearsal(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2 pt-4 border-t border-[#242424] flex flex-col gap-3">
      <h3 className="text-[12px] text-[#71717a] m-0 uppercase tracking-wide">Formation</h3>

      <div className="rounded-[10px] border border-[#2a2a2a] bg-[#0F0F0F]">
        <FormationPreview team={current} height={170} />
      </div>

      <div className="flex flex-col gap-1.5">
        {current.map((m) => {
          const lead = LEADS.has(m.role);
          const [lo, hi] = LIMITS[m.role] ?? [0, 3];
          return (
            <div key={m.role} className="flex items-center gap-2 text-[12px]">
              <span className="capitalize text-[#d4d4d8] w-16 shrink-0">{m.role}</span>
              {lead ? (
                <span className="text-[#52525b] w-[68px] text-center">leads</span>
              ) : (
                <div className="flex items-center gap-1.5 w-[68px] justify-center">
                  <button
                    onClick={() => bump(m.role, -1)}
                    disabled={(m.count ?? 1) <= lo}
                    className="w-5 h-5 rounded bg-[#242424] border border-[#2a2a2a] text-[#d4d4d8] disabled:opacity-40 cursor-pointer leading-none"
                  >
                    −
                  </button>
                  <span className="w-4 text-center text-[#e4e4e7]">{m.count ?? 1}</span>
                  <button
                    onClick={() => bump(m.role, 1)}
                    disabled={(m.count ?? 1) >= hi}
                    className="w-5 h-5 rounded bg-[#242424] border border-[#2a2a2a] text-[#d4d4d8] disabled:opacity-40 cursor-pointer leading-none"
                  >
                    +
                  </button>
                </div>
              )}
              <label className="flex items-center gap-1 text-[#71717a] ml-auto">
                $
                <input
                  type="number"
                  step="0.05"
                  min="0.02"
                  value={m.budget_usd ?? 0.1}
                  onChange={(e) => setBudget(m.role, Number(e.target.value))}
                  className="w-14 bg-[#0F0F0F] border border-[#2a2a2a] rounded px-1.5 py-0.5 text-[#d4d4d8] outline-none"
                />
              </label>
            </div>
          );
        })}
      </div>

      <button
        onClick={shadowHunt}
        disabled={busy}
        className="self-start rounded-lg border border-[#2a2a2a] text-[#d4d4d8] hover:text-white px-3 py-1.5 text-[12px] cursor-pointer bg-transparent disabled:opacity-60"
      >
        {busy ? "Rehearsing…" : "Shadow Hunt — rehearse cost"}
      </button>

      {rehearsal && (
        <div className="text-[11.5px] text-[#a1a1aa] flex flex-col gap-1">
          <span>
            ~${rehearsal.est_cost_usd.toFixed(2)} · ~{Math.round(rehearsal.est_time_s / 6) / 10}m ·{" "}
            {rehearsal.scouts} scout{rehearsal.scouts === 1 ? "" : "s"}
          </span>
          {rehearsal.warnings.map((w) => (
            <span key={w} className="text-[#e6a23c]">
              {w}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
