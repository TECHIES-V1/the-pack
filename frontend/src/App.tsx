// App shell. A thin nav over three views: the Door (S1, placeholder), the Territory (S3,
// fed by the sample stream so it lights up without a backend), and the states gallery.
// Real routing + the full screen set (Doc 02) land in WS-B/WS-C/WS-D.

import { useEffect, useState } from "react";

import { Territory } from "@/canvas/Territory";
import { DoorPage } from "@/pages/DoorPage";
import { PlanPage } from "@/pages/PlanPage";
import { StatesGallery } from "@/pages/StatesGallery";
import { useHuntStore } from "@/store/huntStore";
import { sampleStream } from "@/demo/sampleStream";

type View = "door" | "territory" | "gallery" | "plan";

function getInitialView(): View {
  const path = window.location.pathname.replace(/^\//, "");
  if (path === "door" || path === "territory" || path === "gallery") return path;
  if (path.startsWith("plan")) return "plan";
  return "territory";
}

export default function App() {
  const [view, setView] = useState<View>(getInitialView);

  function navigate(v: View) {
    setView(v);
    window.history.pushState({}, "", `/${v}`);
  }

  useEffect(() => {
    function onPopState() {
      setView(getInitialView());
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const huntView = useHuntStore((s) => s.view);
  const apply = useHuntStore((s) => s.apply);
  const reset = useHuntStore((s) => s.reset);

  // Replay the sample stream into the store, one event at a time — the canvas renders
  // purely from what the reducer produces (the golden rule).
  useEffect(() => {
    if (view !== "territory") return;
    reset();
    let i = 0;
    const id = setInterval(() => {
      if (i >= sampleStream.length) {
        clearInterval(id);
        return;
      }
      apply(sampleStream[i++]);
    }, 350);
    return () => clearInterval(id);
  }, [view, apply, reset]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "10px 18px",
          background: "var(--ink)",
          color: "var(--bone)",
        }}
      >
        <strong style={{ letterSpacing: 0.4 }}>Pack</strong>
        <nav style={{ display: "flex", gap: 8 }}>
          {(["door", "territory", "gallery"] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => navigate(v)}
              style={{
                background: view === v ? "var(--accent)" : "transparent",
                color: view === v ? "var(--ink)" : "var(--bone)",
                border: "1px solid var(--accent)",
                borderRadius: 8,
                padding: "4px 10px",
                cursor: "pointer",
                textTransform: "capitalize",
              }}
            >
              {v}
            </button>
          ))}
        </nav>
        {view === "territory" && (
          <span style={{ marginLeft: "auto", fontSize: 13, opacity: 0.85 }}>
            Boundary {huntView.boundary.pct.toFixed(0)}% · {huntView.state}
          </span>
        )}
      </header>

      <main style={{ flex: 1, minHeight: 0 }}>
        {view === "door" && <DoorPage />}
        {view === "plan" && <PlanPage />}
        {view === "territory" && <Territory view={huntView} />}
        {view === "gallery" && <StatesGallery />}
      </main>
    </div>
  );
}
