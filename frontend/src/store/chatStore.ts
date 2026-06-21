// Conversation store (Zustand) — the ONE thread of talk with Alpha, shared across the Door and the
// hunt screen so the conversation never dies on navigation.
//
// Persisted to localStorage so the chat SURVIVES A REFRESH (it used to evaporate). `huntId` marks
// which hunt this conversation belongs to, so opening a different hunt resets the thread while
// Door → plan and a page refresh keep it. `pending` is transient and deliberately not persisted.

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { stripDashes } from "@/lib/text";

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
  /** Drop the trailing Alpha reply so the last user turn can be re-answered (Regenerate). */
  dropLastAlpha: () => void;
  /** Keep turns[0..index-1]; removes that turn and everything after it (Edit & resend). */
  truncateFrom: (index: number) => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      turns: [],
      pending: false,
      proposal: null,
      huntId: null,
      addUser: (text) => set((s) => ({ turns: [...s.turns, { role: "user", text }] })),
      // Everything Alpha says is cleansed of em/en dashes before it ever reaches the screen.
      addAlpha: (text) => set((s) => ({ turns: [...s.turns, { role: "alpha", text: stripDashes(text) }] })),
      setPending: (pending) => set({ pending }),
      propose: (brief) => set({ proposal: { brief: stripDashes(brief) } }),
      clearProposal: () => set({ proposal: null }),
      bindHunt: (huntId) => set({ huntId }),
      reset: () => set({ turns: [], pending: false, proposal: null, huntId: null }),
      dropLastAlpha: () =>
        set((s) => {
          const t = [...s.turns];
          if (t.length && t[t.length - 1].role === "alpha") t.pop();
          return { turns: t, proposal: null };
        }),
      truncateFrom: (index) => set((s) => ({ turns: s.turns.slice(0, index), proposal: null })),
    }),
    {
      name: "pack-chat",
      // Persist the conversation, not the transient "thinking" flag.
      partialize: (s) => ({ turns: s.turns, proposal: s.proposal, huntId: s.huntId }),
    },
  ),
);
