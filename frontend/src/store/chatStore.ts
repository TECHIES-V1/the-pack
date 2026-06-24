// Conversation store (Zustand) — the ONE thread of talk with Alpha, shared across the Door and the
// hunt screen so the conversation never dies on navigation.
//
// Persisted to localStorage so the chat SURVIVES A REFRESH (it used to evaporate). `huntId` marks
// which hunt this conversation belongs to, so opening a different hunt resets the thread while
// Door → plan and a page refresh keep it. `pending` is transient and deliberately not persisted.

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { stripDashes } from "@/lib/text";
import { api } from "@/net/api";

export interface ChatTurn {
  role: "user" | "alpha";
  text: string;
}

interface ChatStore {
  turns: ChatTurn[];
  pending: boolean;
  proposal: { brief: string } | null;
  huntId: string | null;
  abortFn: (() => void) | null;
  addUser: (text: string) => void;
  addAlpha: (text: string) => void;
  /** Open an empty Alpha bubble to receive streaming tokens. */
  startAlpha: () => void;
  /** Append a streaming token to the last Alpha turn (no backend save yet). */
  addAlphaToken: (token: string) => void;
  /** Strip dashes and persist the completed streaming turn to the backend. */
  commitAlpha: () => void;
  setPending: (pending: boolean) => void;
  propose: (brief: string) => void;
  clearProposal: () => void;
  bindHunt: (huntId: string) => void;
  reset: () => void;
  /** Drop the trailing Alpha reply so the last user turn can be re-answered (Regenerate). */
  dropLastAlpha: () => void;
  /** Keep turns[0..index-1]; removes that turn and everything after it (Edit & resend). */
  truncateFrom: (index: number) => void;
  /** Replace the whole thread (used to hydrate from the backend's saved messages). */
  hydrate: (turns: ChatTurn[]) => void;
  setAbortFn: (fn: (() => void) | null) => void;
  abortAlpha: () => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      turns: [],
      pending: false,
      proposal: null,
      huntId: null,
      abortFn: null,
      addUser: (text) => {
        set((s) => ({ turns: [...s.turns, { role: "user", text }] }));
        const hid = get().huntId;
        if (hid) api.saveMessage(hid, "user", text).catch(() => {});
      },
      // Everything Alpha says is cleansed of em/en dashes before it ever reaches the screen.
      addAlpha: (text) => {
        const clean = stripDashes(text);
        set((s) => ({ turns: [...s.turns, { role: "alpha", text: clean }] }));
        const hid = get().huntId;
        if (hid) api.saveMessage(hid, "alpha", clean).catch(() => {});
      },
      startAlpha: () =>
        set((s) => ({ turns: [...s.turns, { role: "alpha", text: "" }] })),
      addAlphaToken: (token) =>
        set((s) => {
          const turns = [...s.turns];
          const last = turns[turns.length - 1];
          if (last?.role === "alpha") turns[turns.length - 1] = { role: "alpha", text: last.text + token };
          return { turns };
        }),
      commitAlpha: () => {
        const { turns, huntId } = get();
        const last = turns[turns.length - 1];
        if (!last || last.role !== "alpha") return;
        const clean = stripDashes(last.text);
        set((s) => {
          const t = [...s.turns];
          t[t.length - 1] = { role: "alpha", text: clean };
          return { turns: t };
        });
        if (huntId) api.saveMessage(huntId, "alpha", clean).catch(() => {});
      },
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
      hydrate: (turns) => set({ turns }),
      setAbortFn: (fn) => set({ abortFn: fn }),
      abortAlpha: () => { get().abortFn?.(); set({ abortFn: null }); },
    }),
    {
      name: "pack-chat",
      // Persist the conversation, not the transient "thinking" flag.
      partialize: (s) => ({ turns: s.turns, proposal: s.proposal, huntId: s.huntId }),
    },
  ),
);
