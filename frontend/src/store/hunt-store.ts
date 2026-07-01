import { create } from 'zustand'
import { huntReducer, initialHuntState } from '@/events/reducer'
import type { HuntEvent, HuntState } from '@/events/schema'

interface HuntStore {
  state: HuntState
  dispatch: (event: HuntEvent) => void
  reset: () => void
}

export const useHuntStore = create<HuntStore>((set) => ({
  state: initialHuntState,
  dispatch: (event: HuntEvent) =>
    set((store) => ({ state: huntReducer(store.state, event) })),
  reset: () => set({ state: initialHuntState }),
}))