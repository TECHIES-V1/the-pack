// User settings (persisted locally — the build is anonymous-session, so settings attach to the
// browser, not an account). Custom instructions are injected into Alpha's prompt as a system
// message, frontend-side, so no backend change is needed.

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsStore {
  customInstructions: string;
  setCustomInstructions: (v: string) => void;
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      customInstructions: "",
      setCustomInstructions: (customInstructions) => set({ customInstructions }),
    }),
    { name: "pack-settings" },
  ),
);

// Prepend the user's custom instructions as a system turn, if set. Used by the Door + the rail
// before calling /hunts/intake and /hunts/:id/ask.
export function withCustomInstructions<T extends { role: string; content: string }>(
  messages: T[],
): T[] {
  const ci = useSettingsStore.getState().customInstructions.trim();
  if (!ci) return messages;
  const sys = { role: "system", content: `The Packmaster's standing instructions: ${ci}` } as T;
  return [sys, ...messages];
}
