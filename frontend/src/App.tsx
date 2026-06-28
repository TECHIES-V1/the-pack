// App shell + router (Doc 02 §01 routes). When a hunt is in the URL, App connects the live
// gateway stream and feeds the store; every screen renders purely from the event log.
//   /                      Door (S1)
//   /hunt/:id/plan         review + Send  ┐ both render HuntScreen (state-driven:
//   /hunt/:id              live → Return  ┘ plan_ready · hunting · returned)
//   /hunt/:id/tracks       Tracks (S5)
//   /hunt/:id/scorecard    Scorecard (S6)
//   /gallery               states gallery (dev)

import { useEffect, useRef, useState } from "react";
import { MotionConfig } from "framer-motion";

import { DoorPage } from "@/pages/DoorPage";
import { HuntScreen } from "@/pages/HuntScreen";
import { TracksPage } from "@/pages/TracksPage";
import { ScorecardPage } from "@/pages/ScorecardPage";
import { StatesGallery } from "@/pages/StatesGallery";
import { ShareView } from "@/pages/ShareView";
import { LibraryPage } from "@/pages/LibraryPage";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { SettingsModal } from "@/components/settings/SettingsModal";
import { HuntCompleteToast } from "@/components/ui/HuntCompleteToast";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ConnectionBadge } from "@/components/ConnectionBadge";
import { useHuntStore } from "@/store/huntStore";
import { useChatStore } from "@/store/chatStore";
import { useUiStore } from "@/store/uiStore";
import { StreamClient } from "@/net/streamClient";
import { startNewHunt } from "@/lib/nav";

type View = "door" | "hunt" | "tracks" | "scorecard" | "gallery" | "share" | "library" | "notifications";

interface Route {
  view: View;
  huntId: string | null;
  token?: string;
  focus?: string; // v5.6: a wolf id to highlight in Tracks (deep-link from a brief line)
}

function parseRoute(): Route {
  const path = window.location.pathname.replace(/^\//, "");
  if (path.startsWith("hunt/")) {
    const [id, sub] = path.slice("hunt/".length).split("/");
    if (sub === "tracks") {
      const focus = new URLSearchParams(window.location.hash.slice(1)).get("wolf") ?? undefined;
      return { view: "tracks", huntId: id, focus };
    }
    if (sub === "scorecard") return { view: "scorecard", huntId: id };
    return { view: "hunt", huntId: id }; // /hunt/:id and /hunt/:id/plan
  }
  if (path.startsWith("share/")) return { view: "share", huntId: null, token: path.slice("share/".length) };
  if (path === "gallery") return { view: "gallery", huntId: null };
  if (path === "library") return { view: "library", huntId: null };
  if (path === "notifications") return { view: "notifications", huntId: null };
  return { view: "door", huntId: null };
}

const TERMINAL = new Set(["returned", "failed", "stopped_by_user"]);

export default function App() {
  const [route, setRoute] = useState<Route>(parseRoute);
  const [streamStatus, setStreamStatus] = useState<"connecting" | "open" | "closed">("open");
  const huntState = useHuntStore((s) => s.view.state);
  const { setDenOpen, setSettingsOpen, settingsOpen } = useUiStore();

  useEffect(() => {
    const onPop = () => setRoute(parseRoute());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Global keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      const tag = (e.target as HTMLElement).tagName;
      const inInput = tag === "INPUT" || tag === "TEXTAREA";
      if (e.key === "Escape") { setDenOpen(false); setSettingsOpen(false); }
      if (mod && e.key === "k") { e.preventDefault(); setDenOpen((v) => !v); }
      if (mod && e.key === ",") { e.preventDefault(); setSettingsOpen(true); }
      // N for new hunt — only when not typing
      if (e.key === "n" && !mod && !inInput) {
        startNewHunt();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setDenOpen, setSettingsOpen]);

  // Connect the live stream when a hunt enters the URL.
  // Keep it alive when user navigates to Door — stream persists until terminal state.
  const connectedRef = useRef<string | null>(null);
  const clientRef = useRef<StreamClient | null>(null);
  useEffect(() => {
    const id = route.huntId;
    if (!id || connectedRef.current === id) return;
    // Close previous client only if it's a *different* hunt
    clientRef.current?.close();
    useHuntStore.getState().reset();
    if (useChatStore.getState().huntId !== id) {
      useChatStore.getState().reset();
      useChatStore.getState().bindHunt(id);
    }
    const client = new StreamClient(id, {
      onEvent: (ev) => {
        useHuntStore.getState().apply(ev);
        // Close stream once hunt reaches a terminal state to save connections
        if (TERMINAL.has(useHuntStore.getState().view.state)) {
          client.close();
        }
      },
      getResumeSeq: () => useHuntStore.getState().view.lastSeq,
      onStatus: setStreamStatus,
    });
    client.connect();
    clientRef.current = client;
    connectedRef.current = id;
  }, [route.huntId]);

  let page: React.ReactNode;
  if (route.view === "door") page = <DoorPage />;
  else if (route.view === "hunt") page = <HuntScreen />;
  else if (route.view === "tracks") page = <TracksPage huntId={route.huntId ?? ""} focusWolf={route.focus} />;
  else if (route.view === "scorecard") page = <ScorecardPage huntId={route.huntId ?? ""} />;
  else if (route.view === "share") page = <ShareView token={route.token ?? ""} />;
  else if (route.view === "library") page = <LibraryPage />;
  else if (route.view === "notifications") page = <NotificationsPage />;
  else page = <StatesGallery />;

  // Show the connection badge only on a live hunt that hasn't reached a terminal state — a closed
  // stream after the hunt is done is expected, not a failure.
  const showBadge = route.view === "hunt" && !TERMINAL.has(huntState);

  return (
    <MotionConfig reducedMotion="user">
      <ErrorBoundary>{page}</ErrorBoundary>
      {settingsOpen && <SettingsModal />}
      <HuntCompleteToast />
      {showBadge && <ConnectionBadge status={streamStatus} />}
    </MotionConfig>
  );
}
