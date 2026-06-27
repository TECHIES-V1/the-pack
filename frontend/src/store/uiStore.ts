import { create } from "zustand";

interface UiStore {
  denOpen: boolean;
  settingsOpen: boolean;
  // The brief pop-up over the Territory (the reward). Toggled from the chat link and HuntScreen.
  briefOpen: boolean;
  setDenOpen: (v: boolean | ((prev: boolean) => boolean)) => void;
  setSettingsOpen: (v: boolean) => void;
  setBriefOpen: (v: boolean) => void;
}

export const useUiStore = create<UiStore>((set) => ({
  denOpen: false,
  settingsOpen: false,
  briefOpen: false,
  setDenOpen: (v) =>
    set((s) => ({ denOpen: typeof v === "function" ? v(s.denOpen) : v })),
  setSettingsOpen: (v) => set({ settingsOpen: v }),
  setBriefOpen: (v) => set({ briefOpen: v }),
}));
