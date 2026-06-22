// PlanSidebar — the left rail on the hunt screen. Renders the REAL plan Beta proposed
// (steps + the wolves on each, the coordination pattern), not a static blurb. Falls back to a
// short roster while the plan is still forming.

import { useState } from "react";
import { LuPanelRight, LuArrowLeft } from "react-icons/lu";
import type { PlanView } from "@/events/reducer";

const STRATEGY_LABEL: Record<string, string> = {
  orchestrate: "Dynamic orchestrator",
  deep_dive: "Iterative deep-research",
  critique: "Plan-execute-critique",
};

const ROSTER = [
  "Alpha leads and keeps the pack on track",
  "Beta breaks the goal into a plan",
  "Scouts range for ground truth — in parallel",
  "Tracker cross-references what they bring back",
  "Sentinel challenges weak claims",
  "Howler writes the final brief",
];

interface Props {
  plan: PlanView;
  onApprove: () => void;
  onBack: () => void;
}

export function PlanSidebar({ onBack, plan }: Props) {
  const [open, setOpen] = useState(true);
  const steps = plan?.steps ?? [];

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="shrink-0 flex items-start pt-6 px-8 bg-[#1A1A1A] text-[#a1a1aa] hover:text-white transition-colors cursor-pointer m-2 rounded-[12px] border border-[#2a2a2a] overflow-hidden"
      >
        <LuPanelRight size={20} />
      </button>
    );
  }

  return (
    <aside className="w-[300px] shrink-0 flex flex-col bg-[#1A1A1A] text-white overflow-hidden m-2 rounded-[12px] border border-[#2a2a2a]">
      <div className="px-5 pt-5 pb-4 border-b border-[#2a2a2a] flex justify-between items-start">
        <div className="flex flex-col gap-2.5">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-[12px] text-[#a1a1aa] hover:text-white bg-transparent border-none cursor-pointer p-0"
          >
            <LuArrowLeft size={14} /> Home
          </button>
          <h2 className="text-[16px] font-medium tracking-wide m-0 leading-none">The Plan</h2>
          {plan?.pattern && (
            <span className="bg-[#404040] text-[#a1a1aa] text-[11px] font-medium px-3 py-1.5 rounded-full w-fit leading-none">
              {plan.strategy ? STRATEGY_LABEL[plan.strategy] ?? plan.strategy : plan.pattern}
            </span>
          )}
        </div>
        <button
          onClick={() => setOpen(false)}
          className="text-[#a1a1aa] hover:text-white transition-colors bg-transparent border-none cursor-pointer p-0 mt-1"
        >
          <LuPanelRight size={20} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-5 scrollbar-subtle pr-3">
        {steps.length > 0 ? (
          steps.map((step, i) => (
            <div key={step.step_id} className="flex gap-3">
              <div className="shrink-0 w-6 h-6 rounded-full bg-[#242424] border border-[#3a3a3a] flex items-center justify-center text-[12px] text-[#a1a1aa]">
                {i + 1}
              </div>
              <div className="flex flex-col gap-1.5">
                <p className="text-[13px] text-[#e4e4e7] m-0 leading-snug">{step.summary}</p>
                {step.wolves?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {step.wolves.map((w) => (
                      <span
                        key={w}
                        className="text-[10.5px] text-[#a1a1aa] bg-[#0F0F0F] border border-[#2a2a2a] rounded-full px-2 py-0.5 capitalize"
                      >
                        {w}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-[12px] text-[#71717a] m-0">Beta is drawing up the plan…</p>
            {ROSTER.map((line) => (
              <p key={line} className="text-[13px] text-[#a1a1aa] m-0 leading-snug">
                {line}
              </p>
            ))}
          </div>
        )}

        {plan?.assumptions && plan.assumptions.length > 0 && (
          <div className="mt-2 pt-4 border-t border-[#242424] flex flex-col gap-2">
            <h3 className="text-[12px] text-[#71717a] m-0 uppercase tracking-wide">Assumptions</h3>
            {plan.assumptions.map((a) => (
              <p key={a} className="text-[12px] text-[#a1a1aa] m-0 leading-snug">
                · {a}
              </p>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
