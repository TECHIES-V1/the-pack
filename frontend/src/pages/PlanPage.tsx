// The hunt screen — one dark, 3-column view that animates plan → running → done (Doc 02/03):
//   The Pack (left) · the Territory canvas (center) · Chat session (right).
// Renders live from the hunt store; the stream is connected in App for /plan/:hunt_id.

import { PlanSidebar } from "@/components/plan/PlanSidebar";
import { PlanChatSidebar } from "@/components/plan/PlanChatSidebar";
import { Territory } from "@/canvas/Territory";
import { useHuntStore } from "@/store/huntStore";
import type { PlanView } from "@/events/reducer";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function PlanPage() {
  const huntId = window.location.pathname.split("/plan/")[1] ?? "";
  const view = useHuntStore((s) => s.view);

  return (
    <div className="fixed inset-0 bg-door-bg text-white font-sans flex">
      {/* The Pack (static roster — independent of the plan payload). */}
      <PlanSidebar
        plan={(view.plan ?? {}) as PlanView}
        onApprove={() => {}}
        onBack={() => goTo("/door")}
      />

      {/* The Territory canvas, framed like the sidebars. */}
      <div className="flex-1 m-2 rounded-[12px] overflow-hidden border border-[#2a2a2a] bg-[#0F0F0F]">
        <Territory view={view} />
      </div>

      {/* Chat session — narration, Hunt Summary, Hold, artifact. */}
      <PlanChatSidebar huntId={huntId} />
    </div>
  );
}
