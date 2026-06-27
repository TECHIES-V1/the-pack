import { describe, expect, it } from "vitest";

import { buildGraph } from "./Territory";
import type { WolfView } from "@/events/reducer";

function w(wolfId: string, role: string, extra: Partial<WolfView> = {}): WolfView {
  return {
    wolfId,
    role: role as WolfView["role"],
    status: "idle",
    tier: "plus",
    thinking: false,
    sources: 0,
    spendUsd: 0,
    ...extra,
  };
}

describe("buildGraph — the data-driven canvas", () => {
  it("wires N scouts → tracker → sentinel → howler, the Elder, and a clone's lineage", () => {
    const wolves = [
      w("alpha", "alpha"),
      w("beta", "beta"),
      w("scout-1", "scout"),
      w("scout-2", "scout"),
      w("scout-3", "scout"),
      w("tracker", "tracker"),
      w("sentinel", "sentinel"),
      w("howler", "howler"),
      w("elder", "elder"),
      w("scout-4", "scout", { parentId: "scout-1" }), // a mid-hunt clone
    ];
    const { nodes, edges } = buildGraph(wolves);
    const ids = new Set(edges.map((e) => e.id));
    expect(nodes).toHaveLength(10);
    expect(ids.has("beta->scout-1")).toBe(true);
    expect(ids.has("scout-1->tracker")).toBe(true);
    expect(ids.has("tracker->sentinel")).toBe(true);
    expect(ids.has("sentinel->howler")).toBe(true);
    expect(ids.has("alpha->elder")).toBe(true);
    expect(ids.has("scout-1->scout-4")).toBe(true); // clone lineage
  });

  it("links the Doctor to whoever it's healing", () => {
    const wolves = [
      w("alpha", "alpha"),
      w("beta", "beta"),
      w("scout-1", "scout"),
      w("tracker", "tracker"),
      w("doctor", "doctor", { healing: "scout-1", status: "hunting" }),
    ];
    const ids = new Set(buildGraph(wolves).edges.map((e) => e.id));
    expect(ids.has("doctor->scout-1")).toBe(true);
  });
});
