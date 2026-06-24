// The hunt screen — Doc 02 S2/S3/S4 on one route family, driven by hunt state:
//   plan_ready → review (idle pack + Send); hunting/holding → the live canvas;
//   returned → the brief takes center BUT the chat rail stays, so Alpha is still reachable.
// Renders purely from the hunt store. Seams smoothed: honest URL, soft cross-fade, status banner.

import { useLayoutEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PlanSidebar } from "@/components/plan/PlanSidebar";
import { PlanChatSidebar } from "@/components/plan/PlanChatSidebar";
import { HuntStatusBanner } from "@/components/hunt/HuntStatusBanner";
import { DenDrawer } from "@/components/den/DenDrawer";
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

const PRELAUNCH = new Set(["draft", "planning", "plan_ready"]);

export function HuntScreen() {
  const view = useHuntStore((s) => s.view);
  const huntId = huntIdFromPath();
  const returned = view.state === "returned";

  // Honest URL: drop the lying `/plan` slug once the hunt is past planning, so refresh/Back match
  // what's on screen.
  useLayoutEffect(() => {
    if (!PRELAUNCH.has(view.state) && window.location.pathname.endsWith("/plan")) {
      window.history.replaceState({}, "", `/hunt/${huntId}`);
    }
  }, [view.state, huntId]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="fixed inset-0 bg-door-bg text-white font-sans flex flex-col"
    >
      <DenDrawer />
      <HuntStatusBanner state={view.state} />

      <div className="flex-1 min-h-0 flex">
        {/* Left: the pack roster — only while planning/running, not on the Return */}
        {!returned && (
          <PlanSidebar plan={(view.plan ?? {}) as PlanView} onApprove={() => {}} onBack={() => goTo("/?den=open")} />
        )}

        {/* Center: canvas while live, the brief on the Return — cross-faded, not snapped */}
        <div className="flex-1 m-2 rounded-[12px] overflow-hidden border border-[#2a2a2a] bg-[#0F0F0F]">
          <AnimatePresence mode="wait" initial={false}>
            {returned ? (
              <motion.div
                key="brief"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="h-full"
              >
                <DocumentView huntId={huntId} />
              </motion.div>
            ) : (
              <motion.div
                key="canvas"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="h-full"
              >
                <Territory view={view} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right: the conversation — ALWAYS present, the spine of the journey */}
        <PlanChatSidebar huntId={huntId} />
      </div>
    </motion.div>
  );
}
