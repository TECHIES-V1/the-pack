// App shell + router (Doc 02 §01 routes). When a hunt is in the URL, App connects the live
// gateway stream and feeds the store; every screen renders purely from the event log.
//   /                      Door (S1)
//   /hunt/:id/plan         review + Send  ┐ both render HuntScreen (state-driven:
//   /hunt/:id              live → Return  ┘ plan_ready · hunting · returned)
//   /hunt/:id/tracks       Tracks (S5)
//   /hunt/:id/scorecard    Scorecard (S6)
//   /gallery               states gallery (dev)

import { useEffect, useRef, useState } from "react";

import { DoorPage } from "@/pages/DoorPage";
import { HuntScreen } from "@/pages/HuntScreen";
import { TracksPage } from "@/pages/TracksPage";
import { ScorecardPage } from "@/pages/ScorecardPage";
import { StatesGallery } from "@/pages/StatesGallery";
import { useHuntStore } from "@/store/huntStore";
import { StreamClient } from "@/net/streamClient";

type View = "door" | "hunt" | "tracks" | "scorecard" | "gallery";

interface Route {
  view: View;
  huntId: string | null;
}

function parseRoute(): Route {
  const path = window.location.pathname.replace(/^\//, "");
  if (path.startsWith("hunt/")) {
    const [id, sub] = path.slice("hunt/".length).split("/");
    if (sub === "tracks") return { view: "tracks", huntId: id };
    if (sub === "scorecard") return { view: "scorecard", huntId: id };
    return { view: "hunt", huntId: id }; // /hunt/:id and /hunt/:id/plan
  }
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

  // Connect the live stream whenever a hunt is in the URL; keep it alive across plan→run→return.
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
  if (route.view === "hunt") return <HuntScreen />;
  if (route.view === "tracks") return <TracksPage huntId={route.huntId ?? ""} />;
  if (route.view === "scorecard") return <ScorecardPage huntId={route.huntId ?? ""} />;
  return <StatesGallery />;
}
