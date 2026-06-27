// The staged team being shaped on the Plan before launch (v2). Seeded from the proposed plan's
// team; the Formation Edit Panel writes it; PlanChatSidebar's launch reads it into approvePlan's
// edits.team. Kept out of the hunt store (which is a pure reducer over events) — this is pre-launch
// local UI state, reset on a new hunt.

import { create } from "zustand";
import type { TeamMember } from "@/events/reducer";

interface FormationStore {
  team: TeamMember[] | null; // null until seeded from the proposed plan
  setTeam: (team: TeamMember[]) => void;
  reset: () => void;
}

export const useFormationStore = create<FormationStore>((set) => ({
  team: null,
  setTeam: (team) => set({ team }),
  reset: () => set({ team: null }),
}));
