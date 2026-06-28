// Settings — custom instructions + data controls. Anonymous-session build, so this is per-browser
// (no account). Pack doesn't train on your data, stated plainly instead of a fake training toggle.

import { useEffect, useRef, useState } from "react";
import { LuX, LuUpload, LuTrash2, LuFileText } from "react-icons/lu";
import { api, type KbDoc } from "@/net/api";
import { useSettingsStore } from "@/store/settingsStore";
import { useChatStore } from "@/store/chatStore";
import { useUiStore } from "@/store/uiStore";

export function SettingsModal({ onClose }: { onClose?: () => void }) {
  const close = useUiStore((s) => s.setSettingsOpen);
  function dismiss() { close(false); onClose?.(); }
  const { customInstructions, setCustomInstructions } = useSettingsStore();

  // Knowledge base (v4.2) — your local documents the pack researches alongside the web.
  const [docs, setDocs] = useState<KbDoc[]>([]);
  const [busy, setBusy] = useState(false);
  const [kbError, setKbError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Spend across hunts (v5.4) — local tally from each hunt's final totals.
  const [spend, setSpend] = useState<{
    total_usd: number;
    hunts: { hunt_id: string; title: string; cost_usd: number }[];
  } | null>(null);

  useEffect(() => {
    api.listDocuments().then((r) => setDocs(r.documents)).catch(() => {});
    api.getSpend().then(setSpend).catch(() => {});
  }, []);

  async function uploadDoc(file: File) {
    setBusy(true);
    setKbError(null);
    try {
      const doc = await api.addDocument(file);
      setDocs((d) => [doc, ...d]);
    } catch {
      setKbError("Couldn't read that file — try a PDF, doc, text, or CSV.");
    } finally {
      setBusy(false);
    }
  }

  function removeDoc(id: number) {
    setDocs((d) => d.filter((x) => x.id !== id));
    api.deleteDocument(id).catch(() => {});
  }

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

          {/* Knowledge base — your local documents */}
          <section className="flex flex-col gap-2.5">
            <h3 className="text-[13px] font-medium m-0">Knowledge base</h3>
            <p className="text-[12px] text-[#a1a1aa] m-0">
              Add your own documents (PDF, doc, text, CSV). The pack researches them alongside the web
              and cites them in the brief. Local to this device.
            </p>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              accept=".pdf,.csv,.md,.markdown,.txt,.doc,.docx"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadDoc(f);
                e.target.value = "";
              }}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className="self-start flex items-center gap-2 rounded-lg border border-[#2a2a2a] text-[#d4d4d8] hover:text-white px-3.5 py-2 text-[12.5px] cursor-pointer disabled:opacity-50"
            >
              <LuUpload size={14} /> {busy ? "Reading…" : "Add a document"}
            </button>
            {kbError && <p className="text-[12px] text-[#ff6b5e] m-0">{kbError}</p>}
            {docs.length > 0 && (
              <ul className="m-0 p-0 list-none flex flex-col gap-1.5">
                {docs.map((d) => (
                  <li
                    key={d.id}
                    className="flex items-center gap-2 rounded-lg bg-[#0F0F0F] border border-[#2a2a2a] px-3 py-2"
                  >
                    <LuFileText size={14} className="text-[#71717a] shrink-0" />
                    <span className="flex-1 text-[12.5px] text-[#d4d4d8] truncate">{d.name}</span>
                    <span className="text-[11px] text-[#52525b]">{(d.chars / 1000).toFixed(1)}k</span>
                    <button
                      onClick={() => removeDoc(d.id)}
                      className="text-[#71717a] hover:text-[#ff6b5e] cursor-pointer bg-transparent border-none p-0.5"
                      aria-label={`Remove ${d.name}`}
                    >
                      <LuTrash2 size={13} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Spend across hunts */}
          {spend && (
            <section className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between">
                <h3 className="text-[13px] font-medium m-0">Spend</h3>
                <span className="text-[13px] text-white tabular-nums">
                  ${spend.total_usd.toFixed(4)} <span className="text-[#71717a]">all hunts</span>
                </span>
              </div>
              {spend.hunts.length === 0 ? (
                <p className="text-[12px] text-[#71717a] m-0">No spend yet — your hunts are free so far.</p>
              ) : (
                <ul className="m-0 p-0 list-none flex flex-col gap-1">
                  {spend.hunts.slice(0, 6).map((h) => (
                    <li
                      key={h.hunt_id}
                      className="flex items-center justify-between gap-3 text-[12px] text-[#a1a1aa]"
                    >
                      <span className="truncate">{h.title}</span>
                      <span className="tabular-nums shrink-0">${h.cost_usd.toFixed(4)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

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
