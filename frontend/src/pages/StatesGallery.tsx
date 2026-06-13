// States gallery (Doc 03 §8) — every component in every state, for design review and demo
// screenshots. Built against synthetic data, never a live engine.

import { WolfCard, type WolfNodeData } from "@/canvas/WolfNode";
import type { WolfStatus } from "@/events/types";

const STATES: WolfStatus[] = ["idle", "hunting", "talking", "holding", "stray", "done", "thinking"];

function Cell({ status }: { status: WolfStatus }) {
  const data: WolfNodeData = {
    wolfId: "scout-1",
    role: status === "thinking" ? "sentinel" : "scout",
    status,
    tier: "plus",
    thinking: status === "thinking",
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
      <code style={{ fontSize: 12, color: "var(--ink-soft)" }}>{status}</code>
      <WolfCard data={data} />
    </div>
  );
}

export function StatesGallery() {
  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginTop: 0 }}>WolfNode — state matrix</h2>
      <p style={{ color: "var(--ink-soft)" }}>
        Doc 03 §6. Every state visibly distinct. No state changes without an event.
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 28 }}>
        {STATES.map((s) => (
          <Cell key={s} status={s} />
        ))}
      </div>
    </div>
  );
}
