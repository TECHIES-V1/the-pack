// Conversation store (Zustand) — the ONE thread of talk with Alpha, shared across the Door and the
// hunt screen so the conversation never dies on navigation.
//
// This holds chat only (what Alpha and the Packmaster said). Hunt truth still lives in huntStore,
// fed by the event stream. `huntId` marks which hunt this conversation belongs to, so opening a
// different hunt resets the thread while Door → plan keeps it.

import { create } from "zustand";

export interface ChatTurn {
  role: "user" | "alpha";
  text: string;
}

interface ChatStore {
  turns: ChatTurn[];
  pending: boolean;
  proposal: { brief: string } | null;
  huntId: string | null;
  addUser: (text: string) => void;
  addAlpha: (text: string) => void;
  setPending: (pending: boolean) => void;
  propose: (brief: string) => void;
  clearProposal: () => void;
  bindHunt: (huntId: string) => void;
  reset: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  turns: [],
  pending: false,
  proposal: null,
  huntId: null,
  addUser: (text) => set((s) => ({ turns: [...s.turns, { role: "user", text }] })),
  addAlpha: (text) => set((s) => ({ turns: [...s.turns, { role: "alpha", text }] })),
  setPending: (pending) => set({ pending }),
  propose: (brief) => set({ proposal: { brief } }),
  clearProposal: () => set({ proposal: null }),
  bindHunt: (huntId) => set({ huntId }),
  reset: () => set({ turns: [], pending: false, proposal: null, huntId: null }),
}));
