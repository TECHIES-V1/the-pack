// Hunt store (Zustand). Thin wrapper around the pure reducer (Doc 03 §4).
//
//   WS / SSE client -> event queue -> reducer (pure) -> hunt store (Zustand)
//
// The store holds ONLY what the reducer produces. Components subscribe; they never compute
// truth. Commands go over REST (see api.ts, later); truth comes back on the stream.

import { create } from "zustand";

import { initialHuntView, reduce, type HuntView } from "@/events/reducer";
import type { PackEvent } from "@/events/types";

interface HuntStore {
  view: HuntView;
  apply: (ev: PackEvent) => void;
  applyMany: (events: PackEvent[]) => void;
  reset: () => void;
}

export const useHuntStore = create<HuntStore>((set) => ({
  view: initialHuntView(),
  apply: (ev) => set((s) => ({ view: reduce(s.view, ev) })),
  applyMany: (events) => set((s) => ({ view: events.reduce(reduce, s.view) })),
  reset: () => set({ view: initialHuntView() }),
}));
