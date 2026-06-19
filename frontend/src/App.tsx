// App shell + router. Views: Door (S1), the hunt screen (Plan/Territory, S2/S3), the artifact
// reading view, and the states gallery. When a hunt is in the URL, App connects the live
// gateway stream and feeds the store — every screen then renders purely from the event log.

import { useEffect, useRef, useState } from "react";

import { DoorPage } from "@/pages/DoorPage";
import { PlanPage } from "@/pages/PlanPage";
import { ArtifactPage } from "@/pages/ArtifactPage";
import { TracksPage } from "@/pages/TracksPage";
import { ScorecardPage } from "@/pages/ScorecardPage";
import { StatesGallery } from "@/pages/StatesGallery";
import { useHuntStore } from "@/store/huntStore";
import { StreamClient } from "@/net/streamClient";

type View = "door" | "plan" | "artifact" | "tracks" | "scorecard" | "gallery";

interface Route {
  view: View;
  huntId: string | null;
}

function parseRoute(): Route {
  const path = window.location.pathname.replace(/^\//, "");
  if (path.startsWith("plan/")) return { view: "plan", huntId: path.slice("plan/".length) };
  if (path.startsWith("artifact/")) return { view: "artifact", huntId: path.slice("artifact/".length) };
  if (path.startsWith("tracks/")) return { view: "tracks", huntId: path.slice("tracks/".length) };
  if (path.startsWith("scorecard/")) return { view: "scorecard", huntId: path.slice("scorecard/".length) };
  if (path === "gallery") return { view: "gallery", huntId: null };
  return { view: "door", huntId: null };
}

export default function App() {
  const [route, setRoute] = useState<Route>(parseRoute);

  useEffect(() => {
    const onPop = () => setRoute(parseRoute());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Connect the live stream whenever a hunt is in the URL; keep it alive across plan↔artifact.
  const connectedRef = useRef<string | null>(null);
  const clientRef = useRef<StreamClient | null>(null);
  useEffect(() => {
    const id = route.huntId;
    if (!id || connectedRef.current === id) return;
    clientRef.current?.close();
    useHuntStore.getState().reset();
    const client = new StreamClient(id, {
      onEvent: (ev) => useHuntStore.getState().apply(ev),
      getResumeSeq: () => useHuntStore.getState().view.lastSeq,
    });
    client.connect();
    clientRef.current = client;
    connectedRef.current = id;
  }, [route.huntId]);

  if (route.view === "door") return <DoorPage />;
  if (route.view === "plan") return <PlanPage />;
  if (route.view === "artifact") return <ArtifactPage huntId={route.huntId ?? ""} />;
  if (route.view === "tracks") return <TracksPage huntId={route.huntId ?? ""} />;
  if (route.view === "scorecard") return <ScorecardPage huntId={route.huntId ?? ""} />;
  return <StatesGallery />;
}
