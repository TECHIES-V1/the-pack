import { useEffect } from "react";
import { PlanSidebar } from "@/components/plan/PlanSidebar";
import { PlanChatSidebar } from "@/components/plan/PlanChatSidebar";
import { useHuntStore } from "@/store/huntStore";

// Minimal fixture stream: just enough to reach plan_ready.
const PLAN_STREAM = [
  {
    event_id: "evt_p0",
    hunt_id: "demo",
    seq: 0,
    ts: new Date().toISOString(),
    type: "hunt_created" as const,
    actor: "user",
    payload: { source: "typed", raw_input_ref: "art_demo" },
  },
  {
    event_id: "evt_p1",
    hunt_id: "demo",
    seq: 1,
    ts: new Date().toISOString(),
    type: "plan_proposed" as const,
    actor: "beta",
    payload: {
      steps: [
        { step_id: "s1", summary: "Range for BNPL market players", wolves: ["scout-1", "scout-2", "scout-3"] },
        { step_id: "s2", summary: "Cross-reference and extract claims", wolves: ["tracker"] },
        { step_id: "s3", summary: "Draft the briefing with citations", wolves: ["howler"] },
      ],
      wolves: ["scout-1", "scout-2", "scout-3", "tracker", "sentinel", "howler"],
      pattern: "parallel_then_merge",
      assumptions: ["consumer BNPL", "2024 to 2026", "briefing doc"],
      est_cost: 0.60,
      est_time: 210,
    },
  },
];

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function PlanPage() {
  const huntId = window.location.pathname.split("/plan/")[1] ?? "unknown";
  const { view, applyMany, reset } = useHuntStore();

  useEffect(() => {
    reset();
    applyMany(PLAN_STREAM);
  }, [huntId, reset, applyMany]);

  return (
    <div className="fixed inset-0 bg-door-bg text-white font-sans flex">
      {view.plan && (
        <PlanSidebar
          plan={view.plan}
          onApprove={() => console.log("approve", huntId)}
          onBack={() => goTo("/door")}
        />
      )}

      <div className="flex-1 flex flex-col items-center justify-center gap-3">
        <p className="text-door-dim text-sm tracking-wide uppercase">
          {view.plan ? "Review the plan" : "Planning…"}
        </p>
        <h1 className="text-[32px] font-normal tracking-tight m-0">
          {view.plan ? "Ready when you are" : "Coming soon"}
        </h1>
        <p className="text-door-dim text-xs font-mono">{huntId}</p>
        {!view.plan && (
          <button
            onClick={() => goTo("/door")}
            className="mt-4 text-[13px] text-door-dim hover:text-white transition-colors border border-door-border rounded-lg px-4 py-2 bg-transparent cursor-pointer font-sans"
          >
            ← Back to Door
          </button>
        )}
      </div>

      {view.plan && <PlanChatSidebar />}
    </div>
  );
}
