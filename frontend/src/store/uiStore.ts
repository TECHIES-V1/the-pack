import { create } from "zustand";

interface UiStore {
  denOpen: boolean;
  settingsOpen: boolean;
  setDenOpen: (v: boolean | ((prev: boolean) => boolean)) => void;
  setSettingsOpen: (v: boolean) => void;
}

export const useUiStore = create<UiStore>((set) => ({
  denOpen: false,
  settingsOpen: false,
  setDenOpen: (v) =>
    set((s) => ({ denOpen: typeof v === "function" ? v(s.denOpen) : v })),
  setSettingsOpen: (v) => set({ settingsOpen: v }),
}));
