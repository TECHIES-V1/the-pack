// The hunt screen — Doc 02 S2/S3/S4 on one route family, driven by hunt state:
//   /hunt/:id/plan and /hunt/:id render this. plan_ready → review (idle pack + Send);
//   hunting/holding → the live canvas; returned → the Return (document takes center).
// Renders purely from the hunt store.

import { PlanSidebar } from "@/components/plan/PlanSidebar";
import { PlanChatSidebar } from "@/components/plan/PlanChatSidebar";
import { Territory } from "@/canvas/Territory";
import { DocumentView } from "@/components/output/DocumentView";
import { useHuntStore } from "@/store/huntStore";
import type { PlanView } from "@/events/reducer";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function huntIdFromPath(): string {
  const m = window.location.pathname.match(/^\/hunt\/([^/]+)/);
  return m ? m[1] : "";
}

export function HuntScreen() {
  const view = useHuntStore((s) => s.view);
  const huntId = huntIdFromPath();

  // The Return: the canvas recedes, the deliverable takes center.
  if (view.state === "returned") return <DocumentView huntId={huntId} />;

  return (
    <div className="fixed inset-0 bg-door-bg text-white font-sans flex">
      <PlanSidebar
        plan={(view.plan ?? {}) as PlanView}
        onApprove={() => {}}
        onBack={() => goTo("/")}
      />
      <div className="flex-1 m-2 rounded-[12px] overflow-hidden border border-[#2a2a2a] bg-[#0F0F0F]">
        <Territory view={view} />
      </div>
      <PlanChatSidebar huntId={huntId} />
    </div>
  );
}
