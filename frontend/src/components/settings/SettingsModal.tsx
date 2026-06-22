// Settings — custom instructions + data controls. Anonymous-session build, so this is per-browser
// (no account). Pack doesn't train on your data, stated plainly instead of a fake training toggle.

import { LuX } from "react-icons/lu";
import { useSettingsStore } from "@/store/settingsStore";
import { useChatStore } from "@/store/chatStore";
import { useUiStore } from "@/store/uiStore";

export function SettingsModal({ onClose }: { onClose?: () => void }) {
  const close = useUiStore((s) => s.setSettingsOpen);
  function dismiss() { close(false); onClose?.(); }
  const { customInstructions, setCustomInstructions } = useSettingsStore();

  function clearConversation() {
    useChatStore.getState().reset();
    dismiss();
  }

  function clearAllData() {
    try {
      localStorage.removeItem("pack-chat");
      localStorage.removeItem("pack-settings");
    } catch {
      /* ignore */
    }
    useChatStore.getState().reset();
    setCustomInstructions("");
    dismiss();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onClick={dismiss}
    >
      <div
        className="w-[min(520px,94vw)] max-h-[85vh] overflow-y-auto bg-[#1A1A1A] border border-[#2a2a2a] rounded-2xl text-white scrollbar-subtle"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a2a] sticky top-0 bg-[#1A1A1A]">
          <h2 className="text-[16px] font-medium m-0">Settings</h2>
          <button className="text-[#a1a1aa] hover:text-white" onClick={dismiss} aria-label="Close settings">
            <LuX size={18} />
          </button>
        </header>

        <div className="px-6 py-5 flex flex-col gap-7">
          {/* Custom instructions */}
          <section className="flex flex-col gap-2">
            <h3 className="text-[13px] font-medium m-0">Custom instructions</h3>
            <p className="text-[12px] text-[#a1a1aa] m-0">
              How should Alpha talk to you and approach your work? This is applied to every conversation.
            </p>
            <textarea
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              placeholder="e.g. I'm a founder in fintech. Be concise, lead with the answer, and always flag assumptions."
              rows={5}
              className="w-full resize-y bg-[#0F0F0F] border border-[#2a2a2a] rounded-lg p-3 text-[13px] text-white outline-none focus:border-[#404040] placeholder:text-[#52525b]"
            />
          </section>

          {/* Data controls */}
          <section className="flex flex-col gap-3">
            <h3 className="text-[13px] font-medium m-0">Your data</h3>
            <p className="text-[12px] text-[#a1a1aa] m-0">
              Pack does not train on your conversations. Everything here lives in this browser only —
              there's no account.
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={clearConversation}
                className="rounded-lg border border-[#2a2a2a] text-[#d4d4d8] hover:text-white px-3.5 py-2 text-[12.5px] cursor-pointer"
              >
                Clear this conversation
              </button>
              <button
                onClick={clearAllData}
                className="rounded-lg border border-[#e03a2f]/40 text-[#ff6b5e] hover:bg-[#e03a2f]/10 px-3.5 py-2 text-[12.5px] cursor-pointer"
              >
                Clear all saved data
              </button>
            </div>
          </section>

          {/* Appearance — honest about the current state */}
          <section className="flex flex-col gap-1.5">
            <h3 className="text-[13px] font-medium m-0">Appearance</h3>
            <p className="text-[12px] text-[#71717a] m-0">Dark theme. A light theme is on the way.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
