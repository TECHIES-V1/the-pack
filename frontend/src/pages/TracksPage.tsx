// Tracks — the full, honest record of a hunt (Doc 02/03). Reads the event log straight from
// the engine (GET /hunts/:id/tracks/export) and lays it out as a timeline with the spend total
// and the moments that matter (Standoffs, Strays, the Boundary).

import { useEffect, useRef, useState } from "react";
import { LuX } from "react-icons/lu";
import { api } from "@/net/api";
import type { PackEvent } from "@/events/types";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const NOTE: Record<string, string> = {
  hunt_created: "Hunt opened",
  plan_proposed: "Beta proposed the plan",
  plan_approved: "You approved the plan",
  wolf_spawned: "spawned",
  step_started: "started a step",
  tool_called: "searched",
  tool_result: "got results",
  tokens_spent: "spent",
  step_completed: "finished a step",
  message_passed: "handed off",
  hold_opened: "opened a Hold",
  hold_resolved: "Hold resolved",
  standoff_opened: "challenged a claim",
  standoff_resolved: "Standoff resolved",
  stray_detected: "strayed",
  stray_recovered: "recovered",
  boundary_warning: "Boundary warning",
  boundary_downgrade: "eased to a lighter tier",
  boundary_halt: "Boundary halted the hunt",
  artifact_created: "produced an artifact",
  hunt_completed: "Hunt returned",
  hunt_failed: "Hunt failed",
  hunt_stopped: "Stopped by you",
};

const ACCENT: Record<string, string> = {
  standoff_opened: "text-[#c084fc]",
  standoff_resolved: "text-[#c084fc]",
  stray_detected: "text-[#eb3424]",
  stray_recovered: "text-[#3fb27f]",
  boundary_warning: "text-[#e6a23c]",
  boundary_downgrade: "text-[#e6a23c]",
  boundary_halt: "text-[#eb3424]",
  hunt_completed: "text-[#3fb27f]",
};

export function TracksPage({ huntId, focusWolf }: { huntId: string; focusWolf?: string }) {
  const [events, setEvents] = useState<PackEvent[]>([]);
  const [error, setError] = useState(false);
  const firstHit = useRef<HTMLLIElement>(null);

  useEffect(() => {
    api
      .exportTracks(huntId)
      .then((r) => setEvents((r.events as PackEvent[]) ?? []))
      .catch(() => setError(true));
  }, [huntId]);

  // v5.6: when deep-linked from a brief line, scroll the focused wolf's first event into view.
  useEffect(() => {
    if (focusWolf && events.length) firstHit.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusWolf, events]);

  const spend = [...events].reverse().find((e) => e.type === "tokens_spent");
  const cumulative = spend ? Number(spend.payload.cumulative_usd ?? 0) : 0;

  return (
    <div className="fixed inset-0 bg-door-bg text-white font-sans flex flex-col">
      <header className="h-12 shrink-0 flex items-center justify-between px-4 border-b border-[#2a2a2a]">
        <h1 className="text-[14px] font-medium m-0">Tracks</h1>
        <button className="p-2 text-[#a1a1aa] hover:text-white" onClick={() => goTo(`/hunt/${huntId}`)}>
          <LuX size={16} />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-8 scrollbar-subtle">
        <div className="max-w-[760px] mx-auto flex flex-col gap-5">
          <div className="flex gap-8 text-[13px] text-[#a1a1aa]">
            <span>{events.length} events</span>
            <span>${cumulative.toFixed(2)} spent</span>
            <span className="font-mono text-[12px]">{huntId}</span>
          </div>

          {error && <p className="text-[#e03a2f] text-[13px]">Couldn't load the log — is the engine running?</p>}

          {focusWolf && (
            <p className="text-[12px] text-[#5b9bd5] m-0">
              Tracing <span className="font-mono">{focusWolf}</span> — its steps are highlighted below.
            </p>
          )}

          <ol className="m-0 p-0 list-none flex flex-col">
            {events.map((e, i) => {
              const hit = !!focusWolf && e.actor === focusWolf;
              const isFirstHit = hit && events.findIndex((x) => x.actor === focusWolf) === i;
              return (
                <li
                  key={e.seq}
                  ref={isFirstHit ? firstHit : undefined}
                  className={`flex items-baseline gap-3 py-1.5 border-b border-[#1f1f1f] ${
                    hit ? "bg-[#5b9bd5]/10 -mx-2 px-2 rounded" : ""
                  }`}
                >
                  <span className="text-[11px] text-[#52525b] font-mono w-8 shrink-0">{e.seq}</span>
                  <span className={`text-[12px] w-20 shrink-0 ${hit ? "text-[#5b9bd5]" : "text-[#71717a]"}`}>
                    {e.actor}
                  </span>
                  <span className={`text-[13px] ${ACCENT[e.type] ?? "text-[#d4d4d8]"}`}>
                    {NOTE[e.type] ?? e.type}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </div>
  );
}
