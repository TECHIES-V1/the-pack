// App shell. A thin nav over three views: the Door (S1, placeholder), the Territory (S3,
// fed by the sample stream so it lights up without a backend), and the states gallery.
// Real routing + the full screen set (Doc 02) land in WS-B/WS-C/WS-D.

import { useEffect, useState } from "react";

import { Territory } from "@/canvas/Territory";
import { StatesGallery } from "@/pages/StatesGallery";
import { useHuntStore } from "@/store/huntStore";
import { sampleStream } from "@/demo/sampleStream";

type View = "door" | "territory" | "gallery";

export default function App() {
  const [view, setView] = useState<View>("territory");
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
              onClick={() => setView(v)}
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
        {view === "door" && (
          <div style={{ display: "grid", placeItems: "center", height: "100%", padding: 24 }}>
            <div style={{ width: "min(640px, 90%)", textAlign: "center" }}>
              <h1 style={{ fontSize: 28 }}>What should the pack hunt down?</h1>
              <input
                aria-label="What should the pack hunt down?"
                placeholder="Type, speak, or drop…"
                style={{
                  width: "100%",
                  padding: "14px 16px",
                  borderRadius: 12,
                  border: "1px solid var(--wolf-idle)",
                  fontSize: 16,
                }}
              />
              <p style={{ color: "var(--ink-soft)", marginTop: 12 }}>
                Door scaffold (S1). OneBox / MicSheet / DropHalo land in WS-B.
              </p>
            </div>
          </div>
        )}
        {view === "territory" && <Territory view={huntView} />}
        {view === "gallery" && <StatesGallery />}
      </main>
    </div>
  );
}
