// StrategyPicker — choose how the pack hunts before you send it (Phase 1/2).
//
// The research strategy shapes the PLAN (it's picked at the Door, before launch) and is
// orthogonal to the autonomy mode picked at approval. Three modes, one tap each.

import type { StrategyName } from "@/net/api";

const OPTIONS: { name: StrategyName; label: string; hint: string }[] = [
  { name: "orchestrate", label: "Orchestrate", hint: "Dynamic — the pack adapts as it learns." },
  { name: "deep_dive", label: "Deep dive", hint: "Iterative — searches, finds gaps, searches again." },
  { name: "critique", label: "Critique", hint: "Rigorous — Sentinel challenges weak claims." },
];

export function StrategyPicker({
  value,
  onChange,
  disabled,
}: {
  value: StrategyName;
  onChange: (s: StrategyName) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5" role="radiogroup" aria-label="Research strategy">
      {OPTIONS.map((o) => {
        const on = value === o.name;
        return (
          <button
            key={o.name}
            type="button"
            role="radio"
            aria-checked={on}
            disabled={disabled}
            title={o.hint}
            onClick={() => onChange(o.name)}
            className={`px-2.5 py-1 rounded-full text-[11.5px] border transition-colors cursor-pointer disabled:opacity-50 ${
              on
                ? "bg-white text-black border-white"
                : "bg-transparent text-[#a1a1aa] border-[#2a2a2a] hover:text-white hover:border-[#3a3a3a]"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
