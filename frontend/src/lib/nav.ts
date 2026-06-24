// Start a genuinely fresh hunt: clear the persisted conversation, then go to the Door. Without the
// reset, the Door reopens on the previous (persisted) chat and "New hunt" looks like it did nothing.

import { useChatStore } from "@/store/chatStore";

export function startNewHunt() {
  useChatStore.getState().reset();
  window.history.pushState({}, "", "/");
  window.dispatchEvent(new PopStateEvent("popstate"));
}
