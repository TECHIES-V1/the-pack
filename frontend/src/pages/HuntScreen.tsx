// The hunt screen — Doc 02 S2/S3/S4 on one route family, driven by hunt state:
//   plan_ready → review (idle pack + Send); hunting/holding → the live canvas;
//   returned → the brief POPS UP over the Territory (the reward), closeable back to the canvas.
// Renders purely from the hunt store. The Territory never unmounts, so there's no flash on the Return.

import { useEffect, useLayoutEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PlanSidebar } from "@/components/plan/PlanSidebar";
import { PlanChatSidebar } from "@/components/plan/PlanChatSidebar";
import { HuntStatusBanner } from "@/components/hunt/HuntStatusBanner";
import { DenDrawer } from "@/components/den/DenDrawer";
import { Territory } from "@/canvas/Territory";
import { DocumentView } from "@/components/output/DocumentView";
import { useHuntStore } from "@/store/huntStore";
import { useUiStore } from "@/store/uiStore";
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

  const briefOpen = useUiStore((s) => s.briefOpen);
  const setBriefOpen = useUiStore((s) => s.setBriefOpen);
  const openedRef = useRef(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Honest URL: drop the lying `/plan` slug once the hunt is past planning, so refresh/Back match
  // what's on screen.
  useLayoutEffect(() => {
    if (!PRELAUNCH.has(view.state) && window.location.pathname.endsWith("/plan")) {
      window.history.replaceState({}, "", `/hunt/${huntId}`);
    }
  }, [view.state, huntId]);

  // A new hunt in view resets the reward state.
  useEffect(() => {
    openedRef.current = false;
    setBriefOpen(false);
  }, [huntId, setBriefOpen]);

  // Auto-open the reward once when the hunt is (or becomes) returned — but never fight a user who
  // closed it.
  useEffect(() => {
    if (returned && !openedRef.current) {
      openedRef.current = true;
      setBriefOpen(true);
    }
  }, [returned, setBriefOpen]);

  // Modal a11y while the brief is open: Escape closes, focus moves in and is restored on close,
  // background scroll is locked, and Tab is trapped inside the dialog.
  const modalOpen = returned && briefOpen;
  useEffect(() => {
    if (!modalOpen) return;
    const prevActive = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setBriefOpen(false);
        return;
      }
      if (e.key === "Tab" && dialogRef.current) {
        const f = dialogRef.current.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),textarea,input,select,[tabindex]:not([tabindex="-1"])',
        );
        if (!f.length) return;
        const first = f[0];
        const last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      prevActive?.focus?.();
    };
  }, [modalOpen, setBriefOpen]);

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
        {/* Left: the pack roster — the full territory stays intact, even behind the reward */}
        <PlanSidebar
          plan={(view.plan ?? {}) as PlanView}
          onApprove={() => {}}
          onBack={() => goTo("/?den=open")}
          huntId={huntId}
          editable={view.state === "plan_ready"}
        />

        {/* Center: the Territory, always mounted. On the Return the brief pops up over it. */}
        <div className="relative flex-1 m-2 rounded-[12px] overflow-hidden border border-[#2a2a2a] bg-[#0F0F0F]">
          <Territory view={view} />
          {view.forging && !returned && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 rounded-full bg-[#1A1A1A] border border-[#2a2a2a] px-3.5 py-1.5 text-[12px] text-[#e4e4e7] shadow-lg">
              <span className="h-2 w-2 rounded-full bg-[#2dd4bf] animate-pulse" />
              Making your files…
            </div>
          )}
          {returned && !briefOpen && (
            <button
              onClick={() => setBriefOpen(true)}
              className="absolute top-3 right-3 z-10 rounded-lg bg-white text-black px-3 py-1.5 text-[13px] font-medium cursor-pointer border-none shadow-lg hover:bg-white/90"
            >
              Open brief →
            </button>
          )}
        </div>

        {/* Right: the conversation — ALWAYS present, the spine of the journey */}
        <PlanChatSidebar huntId={huntId} />
      </div>

      {/* The reward — the brief as a smooth, accessible pop-up over the Territory */}
      <AnimatePresence>
        {modalOpen && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
            onClick={() => setBriefOpen(false)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <motion.div
              ref={dialogRef}
              role="dialog"
              aria-modal="true"
              aria-label="The pack's brief"
              tabIndex={-1}
              onClick={(e) => e.stopPropagation()}
              initial={{ opacity: 0, scale: 0.97, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.97, y: 8 }}
              transition={{ duration: 0.2 }}
              className="w-[min(900px,95vw)] h-[min(88vh,900px)] outline-none overflow-hidden rounded-2xl border border-[#2a2a2a] bg-door-bg shadow-2xl"
            >
              <DocumentView
                huntId={huntId}
                team={view.plan?.team ?? undefined}
                onClose={() => setBriefOpen(false)}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
