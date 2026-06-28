// DocumentView — the Return (Doc 02 §S4). The final brief takes center; the canvas has receded.
// Renders the engine's real drafted text as Markdown (headings, lists, bold, and tables like the
// Span Map). Em-dashes are cleansed. Download / Copy / Save-as-Instinct are wired.

import { useEffect, useState } from "react";
import { LuDownload, LuCopy, LuEllipsis, LuX } from "react-icons/lu";
import { MarkdownReply } from "@/components/chat/MarkdownReply";
import { stripDashes } from "@/lib/text";
import { startNewHunt } from "@/lib/nav";
import { api } from "@/net/api";

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

interface Source {
  n: number;
  label: string;
  by: string;
  verified: boolean;
  url?: string;
  snippet?: string;
}

// The real source dicts the engine stores on the final artifact: {title, url, snippet, by, verified}.
function toSources(raw: unknown): Source[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((s, i) => {
    const o = (s ?? {}) as Record<string, unknown>;
    return {
      n: i + 1,
      label: String(o.title || o.url || `Source ${i + 1}`),
      by: String(o.by || "the pack"),
      verified: Boolean(o.verified),
      url: typeof o.url === "string" ? o.url : undefined,
      snippet: typeof o.snippet === "string" ? o.snippet : undefined,
    };
  });
}

export function DocumentView({ huntId, onClose }: { huntId: string; onClose?: () => void }) {
  const [menu, setMenu] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [noSources, setNoSources] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    api
      .getArtifact(huntId)
      .then((a) => {
        const content =
          (a.content as { text?: string; sources?: unknown; no_sources?: boolean } | null) ?? {};
        if (typeof content.text === "string" && content.text.trim()) {
          setDraft(stripDashes(content.text.trim()));
        }
        setSources(toSources(content.sources));
        setNoSources(Boolean(content.no_sources));
      })
      .catch(() => {});
  }, [huntId]);

  // Title = the first non-empty line (its own heading); body = everything after, so the title
  // never prints twice.
  const lines = draft ? draft.split("\n") : [];
  const firstIdx = lines.findIndex((l) => l.trim());
  const title =
    firstIdx >= 0
      ? lines[firstIdx].replace(/^#+\s*/, "").replace(/\*\*/g, "").trim().slice(0, 160) || "The Pack's brief"
      : "The Pack's brief";
  const body = firstIdx >= 0 ? lines.slice(firstIdx + 1).join("\n").trim() : "";
  const fullText = draft ?? "";

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 1800);
  }

  return (
    <div className="relative h-full w-full bg-door-bg text-white font-sans flex flex-col">
      <header className="h-12 shrink-0 flex items-center justify-between px-4 border-b border-[#2a2a2a]">
        <span className="text-[13px] text-[#a1a1aa] truncate max-w-[50%]">{title}</span>
        <div className="flex items-center gap-1 relative">
          <button
            className="mr-1 rounded-md px-2.5 py-1 text-[12px] text-[#a1a1aa] border border-[#2a2a2a] hover:text-white cursor-pointer"
            onClick={startNewHunt}
          >
            + New hunt
          </button>
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
          <button
            className="p-2 text-[#a1a1aa] hover:text-white"
            title={onClose ? "Close" : "Home"}
            onClick={() => (onClose ? onClose() : goTo("/"))}
          >
            <LuX size={16} />
          </button>
          {menu && (
            <div className="absolute right-0 top-10 z-10 w-44 bg-[#1A1A1A] border border-[#2a2a2a] rounded-lg py-1 text-[13px]">
              <button
                className="w-full text-left px-3 py-2 hover:bg-[#242424]"
                onClick={async () => {
                  setMenu(false);
                  try {
                    const { token } = await api.shareHunt(huntId);
                    await navigator.clipboard?.writeText(`${window.location.origin}/share/${token}`);
                    flash("Share link copied");
                  } catch {
                    flash("Couldn't create link");
                  }
                }}
              >
                Copy share link
              </button>
              <button
                className="w-full text-left px-3 py-2 hover:bg-[#242424]"
                onClick={async () => {
                  setMenu(false);
                  try {
                    const snap = await api.getHunt(huntId);
                    // Store a loadable spec so re-running the instinct seeds the same task + strategy.
                    await api.saveInstinct(snap.task || title, {
                      task: snap.task,
                      strategy: snap.strategy,
                      hunt_id: huntId,
                    });
                    flash("Saved as instinct");
                  } catch {
                    flash("Couldn't save");
                  }
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

      <article className="flex-1 overflow-y-auto px-6 py-10 scrollbar-subtle">
        <div className="max-w-[760px] mx-auto">
          {noSources ? (
            <div className="flex flex-col items-center text-center gap-4 py-20">
              <div className="w-12 h-12 rounded-full border border-[#3a3a3a] flex items-center justify-center text-[#e6a23c] text-xl">
                !
              </div>
              <h1 className="text-[20px] font-medium tracking-tight m-0">No sourced ground</h1>
              <p className="text-[14px] leading-7 text-[#a1a1aa] max-w-[520px] m-0">{draft}</p>
              <button
                onClick={startNewHunt}
                className="mt-1 rounded-lg bg-white text-black px-4 py-2 text-[13px] font-medium cursor-pointer border-none hover:bg-white/90"
              >
                Send the pack again →
              </button>
            </div>
          ) : (
            <>
              <h1 className="text-[28px] font-semibold tracking-tight m-0">{title}</h1>
              <p className="text-[13px] text-[#71717a] mt-2 mb-6">Researched and drafted by Pack</p>
              {draft ? (
                <div className="text-[15px] leading-7 text-[#d4d4d8]">
                  <MarkdownReply text={body} />
                </div>
              ) : (
                <p className="text-[14px] text-[#71717a]">Bringing back the brief…</p>
              )}

              {sources.length > 0 && (
            <div className="mt-10 pt-6 border-t border-[#242424]">
              <h2 className="text-[15px] font-medium m-0 mb-3">Sources</h2>
              <ol className="m-0 pl-5 flex flex-col gap-2.5">
                {sources.map((s) => (
                  <li key={s.n} className="text-[13px] leading-snug">
                    {s.url ? (
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[#5b9bd5] hover:underline"
                      >
                        {s.label}
                      </a>
                    ) : (
                      <span className="text-[#d4d4d8]">{s.label}</span>
                    )}
                    <span className="text-[#71717a]">
                      {" "}
                      — {s.by}
                      {s.verified ? " · read in full" : " · flagged unverified"}
                    </span>
                    {s.snippet && <p className="text-[12px] text-[#71717a] m-0 mt-1">{s.snippet}</p>}
                  </li>
                ))}
              </ol>
            </div>
              )}
            </>
          )}
        </div>
      </article>

      {toast && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-[#1A1A1A] border border-[#2a2a2a] rounded-lg px-4 py-2 text-[13px]">
          {toast}
        </div>
      )}
    </div>
  );
}
