// ChatThread — the ONE chat transcript, shared by the Door and the hunt rail so the conversation
// looks identical and stays continuous across navigation. It reads the shared chatStore.
//
// Auto-scroll is done by setting the container's own scrollTop (NOT element.scrollIntoView, which
// walks up to scrollable ancestors and, inside a position:fixed shell, can scroll the document root
// and shove content out of view — that was the "chat disappeared after a few messages" bug).

import { useLayoutEffect, useRef, type ReactNode } from "react";
import { AlphaAvatar } from "@/components/chat/AlphaAvatar";
import { TypeOut } from "@/components/chat/TypeOut";
import { useChatStore } from "@/store/chatStore";

interface ChatThreadProps {
  className?: string;
  avatarSize?: number;
  textClass?: string;
  bubbleClass?: string;
  /** Optional content rendered after the turns (e.g. the Door's confirm buttons). */
  footer?: ReactNode;
  /** Shown before any turns exist (e.g. the hunt rail's task bubble fallback). */
  empty?: ReactNode;
}

export function ChatThread({
  className = "",
  avatarSize = 26,
  textClass = "text-[14px]",
  bubbleClass = "text-[14px]",
  footer,
  empty,
}: ChatThreadProps) {
  const turns = useChatStore((s) => s.turns);
  const pending = useChatStore((s) => s.pending);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Pin to the newest message by scrolling the container itself — never the document root.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns, pending, footer]);

  return (
    <div ref={scrollRef} className={`overflow-y-auto scrollbar-subtle flex flex-col gap-4 ${className}`}>
      {turns.length === 0 && !pending ? (
        empty
      ) : (
        <>
          {turns.map((t, i) =>
            t.role === "user" ? (
              <div
                key={i}
                className={`bg-[#242424] rounded-2xl px-4 py-2.5 text-[#e4e4e7] self-end max-w-[85%] ${bubbleClass}`}
              >
                {t.text}
              </div>
            ) : (
              <div key={i} className="flex gap-2.5 items-start max-w-[90%]">
                <AlphaAvatar size={avatarSize} />
                <p className={`leading-relaxed text-[#d4d4d8] m-0 pt-0.5 ${textClass}`}>
                  <TypeOut text={t.text} />
                </p>
              </div>
            ),
          )}

          {pending && (
            <div className="flex gap-2.5 items-center">
              <AlphaAvatar size={avatarSize} />
              <span className="text-[13px] text-[#71717a] italic">Alpha is thinking…</span>
            </div>
          )}

          {footer}
        </>
      )}
    </div>
  );
}
