// Public, read-only view of a shared brief (/share/:token). No chat, no hunt id, no actions —
// just the deliverable, rendered as Markdown, with a quiet "make your own" footer.

import { useEffect, useState } from "react";
import { MarkdownReply } from "@/components/chat/MarkdownReply";
import { stripDashes } from "@/lib/text";
import { api } from "@/net/api";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function ShareView({ token }: { token: string }) {
  const [doc, setDoc] = useState<{ title: string; text: string } | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "missing">("loading");

  useEffect(() => {
    api
      .getShared(token)
      .then((d) => {
        const text = (d.content as { text?: string } | null)?.text ?? "";
        setDoc({ title: d.title, text: stripDashes(text.trim()) });
        setState("ok");
      })
      .catch(() => setState("missing"));
  }, [token]);

  // Title = first non-empty line; body = the rest (so the title never prints twice).
  const lines = doc?.text ? doc.text.split("\n") : [];
  const firstIdx = lines.findIndex((l) => l.trim());
  const body = firstIdx >= 0 ? lines.slice(firstIdx + 1).join("\n").trim() : "";

  return (
    <div className="fixed inset-0 bg-door-bg text-white font-sans flex flex-col overflow-hidden">
      <header className="h-12 shrink-0 flex items-center justify-between px-5 border-b border-[#2a2a2a]">
        <span className="text-[14px] font-medium tracking-wide">Pack</span>
        <button
          onClick={() => goTo("/")}
          className="rounded-md px-3 py-1 text-[12px] text-[#a1a1aa] border border-[#2a2a2a] hover:text-white cursor-pointer"
        >
          Make your own
        </button>
      </header>

      <article className="flex-1 overflow-y-auto px-6 py-10 scrollbar-subtle">
        <div className="max-w-[760px] mx-auto">
          {state === "loading" && <p className="text-[14px] text-[#71717a]">Loading…</p>}
          {state === "missing" && (
            <p className="text-[14px] text-[#71717a]">This shared brief isn't available.</p>
          )}
          {state === "ok" && doc && (
            <>
              <h1 className="text-[28px] font-semibold tracking-tight m-0">{doc.title}</h1>
              <p className="text-[13px] text-[#71717a] mt-2 mb-6">Shared from Pack</p>
              <div className="text-[15px] leading-7 text-[#d4d4d8]">
                <MarkdownReply text={body || doc.text} />
              </div>
            </>
          )}
        </div>
      </article>
    </div>
  );
}
