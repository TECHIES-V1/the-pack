// Artifact reading view — the Return (Doc 02 §S, Doc 03). The final brief, with inline
// citations and click-to-trace: clicking a source opens its provenance (where it came from,
// the recording timestamp, verification status). Dark, centered reading column.
//
// NOTE: the article body shown here is representative of the design; wiring the *real* drafted
// text needs a GET /artifacts/:id endpoint on the engine (NEXT) — today the engine stores the
// Howler draft in Postgres but doesn't yet serve it.

import { useEffect, useState } from "react";
import { LuDownload, LuCopy, LuEllipsis, LuX } from "react-icons/lu";
import { api } from "@/net/api";

interface Source {
  n: number;
  label: string;
  by: string;
  verified: boolean;
  ref: string;
  timestamp?: string;
}

const SOURCES: Source[] = [
  { n: 1, label: "CBN Annual Report 2025", by: "Scout-1", verified: true, ref: "art_a_s1" },
  { n: 2, label: "EFInA Financial Inclusion Survey 2025", by: "Scout-2", verified: true, ref: "art_a_s2", timestamp: "04:22" },
  { n: 3, label: "BNPL Coverage", by: "Scout-3", verified: false, ref: "art_a_s3" },
];

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function ArtifactPage({ huntId }: { huntId: string }) {
  const [menu, setMenu] = useState(false);
  const [source, setSource] = useState<Source | null>(null);
  // Pull the REAL drafted text from the engine when there is one.
  const [draft, setDraft] = useState<string | null>(null);
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
    ? draft.split("\n").find((l) => l.trim())?.replace(/^#+\s*/, "").slice(0, 120) ||
      "The Pack's brief"
    : "BNPL in Nigeria: The 5 Million User Claim Doesn't Add Up";
  const paragraphs = draft ? draft.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean) : null;

  return (
    <div className="fixed inset-0 bg-door-bg text-white font-sans flex flex-col">
      {/* Top bar */}
      <header className="h-12 shrink-0 flex items-center justify-between px-4 border-b border-[#2a2a2a]">
        <span className="text-[13px] text-[#a1a1aa] truncate max-w-[60%]">
          Verify this claim: Nigeria has over 5 million active BNPL users…
        </span>
        <div className="flex items-center gap-1 relative">
          <button className="p-2 text-[#a1a1aa] hover:text-white" title="Download"><LuDownload size={16} /></button>
          <button className="p-2 text-[#a1a1aa] hover:text-white" title="Copy"><LuCopy size={16} /></button>
          <button className="p-2 text-[#a1a1aa] hover:text-white" title="More" onClick={() => setMenu((m) => !m)}>
            <LuEllipsis size={16} />
          </button>
          <button className="p-2 text-[#a1a1aa] hover:text-white" title="Close" onClick={() => goTo(`/plan/${huntId}`)}>
            <LuX size={16} />
          </button>
          {menu && (
            <div className="absolute right-0 top-10 z-10 w-44 bg-[#1A1A1A] border border-[#2a2a2a] rounded-lg py-1 text-[13px]">
              <button className="w-full text-left px-3 py-2 hover:bg-[#242424]">Save as instinct</button>
              <button className="w-full text-left px-3 py-2 hover:bg-[#242424]" onClick={() => goTo(`/scorecard/${huntId}`)}>Scorecard</button>
              <button className="w-full text-left px-3 py-2 hover:bg-[#242424]" onClick={() => goTo(`/tracks/${huntId}`)}>Tracks</button>
            </div>
          )}
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Reading column */}
        <article className="flex-1 overflow-y-auto px-6 py-10 scrollbar-subtle">
          <div className="max-w-[720px] mx-auto flex flex-col gap-5">
            <h1 className="text-[28px] font-semibold tracking-tight m-0">{title}</h1>
            <p className="text-[13px] text-[#71717a] m-0">
              Researched and drafted by Pack · The Newsroom
            </p>

            {paragraphs ? (
              paragraphs.map((p, i) => (
                <p key={i} className="text-[15px] leading-7 text-[#d4d4d8] m-0">
                  {p}
                </p>
              ))
            ) : (
              <>
                <p className="text-[15px] leading-7 text-[#d4d4d8] m-0">
                  A claim circulating in Nigerian fintech circles — that the country has over 5
                  million active BNPL users as of 2025 — cannot be verified against any primary
                  source
                  <Cite n={3} onClick={() => setSource(SOURCES[2])} />. Two authoritative figures
                  tell a different story.
                </p>
                <p className="text-[15px] leading-7 text-[#d4d4d8] m-0">
                  The Central Bank of Nigeria's most recent data puts active BNPL users at 2.1
                  million
                  <Cite n={1} onClick={() => setSource(SOURCES[0])} />. A separate 2025 survey by
                  EFInA, the financial-inclusion research body, estimates 3.4 million
                  <Cite n={2} onClick={() => setSource(SOURCES[1])} />. The 5 million figure, widely
                  repeated in media coverage and investor presentations, traces back to no
                  identifiable primary source.
                </p>
                <p className="text-[15px] leading-7 text-[#d4d4d8] m-0">
                  The discrepancy matters. BNPL adoption in Nigeria is growing — that much is not in
                  dispute. But the gap between 2.1 million and 5 million is large enough to affect
                  policy decisions, investment theses, and regulatory posture. Until a primary
                  source surfaces for the higher figure, it should be treated as unverified.
                </p>
              </>
            )}

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

        {/* Provenance panel (click-to-trace) */}
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
    </div>
  );
}

function Cite({ n, onClick }: { n: number; onClick: () => void }) {
  return (
    <sup
      onClick={onClick}
      className="text-[#5b9bd5] cursor-pointer ml-0.5 hover:underline"
      title="Trace this claim"
    >
      [{n}]
    </sup>
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
