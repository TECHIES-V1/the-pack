// TraceRail — the live, scrolling record of real pack actions, docked over the Territory
// (Doc 02 §S3, Phase 2). This is the "trace" half of the combined canvas: the graph shows
// WHERE the pack is, the rail shows WHAT it just did — searches, handoffs, holds, standoffs,
// strays, Boundary moves. Reads purely from the reducer's feed; no logic of its own.

import { useLayoutEffect, useRef } from "react";
import type { FeedLine } from "@/events/reducer";

// Tint each line by what kind of moment it is, so the eye catches the important beats.
function accent(text: string): string {
  const t = text.toLowerCase();
  if (t.includes("holding") || t.includes("hold")) return "#e6a23c";
  if (t.includes("challenged") || t.includes("standoff")) return "#c084fc";
  if (t.includes("stray")) return "#eb3424";
  if (t.includes("boundary")) return "#eab308";
  if (t.includes("searching") || t.includes("search")) return "#5b9bd5";
  return "#3fb27f";
}

export function TraceRail({ feed }: { feed: FeedLine[] }) {
  const ref = useRef<HTMLDivElement>(null);

  // Pin to the newest line by scrolling the rail itself (never the document).
  useLayoutEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [feed.length]);

  return (
    <div className="absolute top-3 right-3 z-10 w-[264px] max-h-[calc(100%-24px)] flex flex-col rounded-[10px] border border-[#262626] bg-[#0d0d0d]/85 backdrop-blur-sm overflow-hidden shadow-lg">
      <div className="px-3 py-2 border-b border-[#222] text-[11px] uppercase tracking-[0.08em] text-[#71717a] flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-[#3fb27f] animate-pulse" />
        Live trace
      </div>
      <div ref={ref} className="flex-1 overflow-y-auto p-2.5 flex flex-col gap-2 scrollbar-subtle">
        {feed.length === 0 ? (
          <div className="text-[11px] text-[#52525b] px-1 py-1">The pack hasn't moved yet.</div>
        ) : (
          feed.map((line) => (
            <div key={line.seq} className="flex gap-2 items-start">
              <span
                className="mt-[5px] w-1.5 h-1.5 rounded-full shrink-0"
                style={{ background: accent(line.text) }}
              />
              <p className="text-[11.5px] leading-snug text-[#c4c4c8] m-0">{line.text}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
