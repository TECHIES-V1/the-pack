// DocumentView — the Return (Doc 02 §S4). The final brief takes center; the canvas has
// receded. Real drafted text from the engine; Download/Copy/Save-as-Instinct are wired.
// Click-to-trace sources are representative until the Howler/Tracker span map exists (NEXT).

import { useEffect, useState } from "react";
import { LuDownload, LuCopy, LuEllipsis, LuX } from "react-icons/lu";
import { api } from "@/net/api";

interface Source {
  n: number;
  label: string;
  by: string;
  verified: boolean;
  timestamp?: string;
}

const SOURCES: Source[] = [
  { n: 1, label: "CBN Annual Report 2025", by: "Scout-1", verified: true },
  { n: 2, label: "EFInA Financial Inclusion Survey 2025", by: "Scout-2", verified: true, timestamp: "04:22" },
  { n: 3, label: "BNPL Coverage", by: "Scout-3", verified: false },
];

const SAMPLE_BODY = [
  "A claim circulating in Nigerian fintech circles — that the country has over 5 million active BNPL users as of 2025 — cannot be verified against any primary source. Two authoritative figures tell a different story.",
  "The Central Bank of Nigeria's most recent data puts active BNPL users at 2.1 million. A separate 2025 survey by EFInA estimates 3.4 million. The 5 million figure traces back to no identifiable primary source.",
  "The discrepancy matters. Until a primary source surfaces for the higher figure, it should be treated as unverified.",
];
const SAMPLE_TITLE = "BNPL in Nigeria: The 5 Million User Claim Doesn't Add Up";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function download(name: string, text: string) {
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function DocumentView({ huntId }: { huntId: string }) {
  const [menu, setMenu] = useState(false);
  const [source, setSource] = useState<Source | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    api
      .getArtifact(huntId)
      .then((a) => {
        const t = (a.content as { text?: string } | null)?.text;
        if (typeof t === "string" && t.trim()) setDraft(t.trim());
      })
      .catch(() => {});
  }, [huntId]);

  const title = draft
    ? draft.split("\n").find((l) => l.trim())?.replace(/^#+\s*/, "").slice(0, 120) || "The Pack's brief"
    : SAMPLE_TITLE;
  const paragraphs = draft ? draft.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean) : SAMPLE_BODY;
  const fullText = `# ${title}\n\n${paragraphs.join("\n\n")}`;

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 1800);
  }

  return (
    <div className="fixed inset-0 bg-door-bg text-white font-sans flex flex-col">
      <header className="h-12 shrink-0 flex items-center justify-between px-4 border-b border-[#2a2a2a]">
        <span className="text-[13px] text-[#a1a1aa] truncate max-w-[60%]">{title}</span>
        <div className="flex items-center gap-1 relative">
          <button className="p-2 text-[#a1a1aa] hover:text-white" title="Download" onClick={() => download(`${huntId}.md`, fullText)}>
            <LuDownload size={16} />
          </button>
          <button
            className="p-2 text-[#a1a1aa] hover:text-white"
            title="Copy"
            onClick={() => navigator.clipboard?.writeText(fullText).then(() => flash("Copied"))}
          >
            <LuCopy size={16} />
          </button>
          <button className="p-2 text-[#a1a1aa] hover:text-white" title="More" onClick={() => setMenu((m) => !m)}>
            <LuEllipsis size={16} />
          </button>
          <button className="p-2 text-[#a1a1aa] hover:text-white" title="Home" onClick={() => goTo("/")}>
            <LuX size={16} />
          </button>
          {menu && (
            <div className="absolute right-0 top-10 z-10 w-44 bg-[#1A1A1A] border border-[#2a2a2a] rounded-lg py-1 text-[13px]">
              <button
                className="w-full text-left px-3 py-2 hover:bg-[#242424]"
                onClick={() => {
                  setMenu(false);
                  api.saveInstinct(title, { hunt_id: huntId }).then(() => flash("Saved as instinct")).catch(() => {});
                }}
              >
                Save as instinct
              </button>
              <button className="w-full text-left px-3 py-2 hover:bg-[#242424]" onClick={() => goTo(`/hunt/${huntId}/scorecard`)}>
                Scorecard
              </button>
              <button className="w-full text-left px-3 py-2 hover:bg-[#242424]" onClick={() => goTo(`/hunt/${huntId}/tracks`)}>
                Tracks
              </button>
            </div>
          )}
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <article className="flex-1 overflow-y-auto px-6 py-10 scrollbar-subtle">
          <div className="max-w-[720px] mx-auto flex flex-col gap-5">
            <h1 className="text-[28px] font-semibold tracking-tight m-0">{title}</h1>
            <p className="text-[13px] text-[#71717a] m-0">Researched and drafted by Pack · The Newsroom</p>
            {paragraphs.map((p, i) => (
              <p key={i} className="text-[15px] leading-7 text-[#d4d4d8] m-0">{p}</p>
            ))}
            <h2 className="text-[15px] font-medium mt-4 mb-1">Sources</h2>
            <ol className="m-0 pl-5 flex flex-col gap-1.5">
              {SOURCES.map((s) => (
                <li key={s.n} className="text-[13px]">
                  <button
                    onClick={() => setSource(s)}
                    className="text-[#5b9bd5] hover:underline bg-transparent border-none p-0 cursor-pointer text-left"
                  >
                    {s.label}
                  </button>
                  <span className="text-[#71717a]"> — {s.by}{s.verified ? "" : " · flagged as unverified"}</span>
                </li>
              ))}
            </ol>
          </div>
        </article>

        {source && (
          <aside className="w-[320px] shrink-0 border-l border-[#2a2a2a] bg-[#1A1A1A] p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-[14px] font-medium m-0">Source</h3>
              <button className="text-[#a1a1aa] hover:text-white" onClick={() => setSource(null)}><LuX size={16} /></button>
            </div>
            <Field label="Source name" value={source.label} />
            <Field label="Brought back by" value={source.by} />
            {source.timestamp && <Field label="Recording timestamp" value={source.timestamp} />}
            <Field
              label="Verification status"
              value={source.verified ? "Verified against the source" : "Flagged — unverified"}
              tone={source.verified ? "ok" : "warn"}
            />
          </aside>
        )}
      </div>

      {toast && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-[#1A1A1A] border border-[#2a2a2a] rounded-lg px-4 py-2 text-[13px]">
          {toast}
        </div>
      )}
    </div>
  );
}

function Field({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" }) {
  const color = tone === "warn" ? "text-[#e6a23c]" : tone === "ok" ? "text-[#3fb27f]" : "text-[#d4d4d8]";
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wide text-[#71717a]">{label}</span>
      <span className={`text-[13px] ${color}`}>{value}</span>
    </div>
  );
}
