// StrategyPicker — choose how the pack hunts before you send it (Phase 1/2).
//
// The research strategy shapes the PLAN (it's picked at the Door, before launch) and is
// orthogonal to the autonomy mode picked at approval. Three modes, one tap each.

import { useEffect, useState } from "react";
import { api, type StrategyName } from "@/net/api";

// Curated product-voice hints (the engine's `pattern` is technical). Keyed by strategy name.
const HINTS: Record<string, string> = {
  orchestrate: "Dynamic — the pack adapts as it learns.",
  deep_dive: "Iterative — searches, finds gaps, searches again.",
  critique: "Rigorous — Sentinel challenges weak claims.",
};

const FALLBACK: { name: StrategyName; label: string; hint: string }[] = [
  { name: "orchestrate", label: "Orchestrate", hint: HINTS.orchestrate },
  { name: "deep_dive", label: "Deep dive", hint: HINTS.deep_dive },
  { name: "critique", label: "Critique", hint: HINTS.critique },
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
  // Labels come from the engine's live catalog so renamed/added strategies surface here; the
  // hardcoded list is just the offline fallback.
  const [options, setOptions] = useState(FALLBACK);
  useEffect(() => {
    api
      .getStrategies()
      .then(({ strategies }) => {
        if (strategies?.length) {
          setOptions(
            strategies.map((s) => ({ name: s.name, label: s.label, hint: HINTS[s.name] ?? s.pattern })),
          );
        }
      })
      .catch(() => {});
  }, []);
  return (
    <div className="flex items-center gap-1.5" role="radiogroup" aria-label="Research strategy">
      {options.map((o) => {
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
