// ChatThread — the ONE chat transcript, shared by the Door and the hunt rail. Reads the chatStore.
//
// Scrolling (the part that was poor): Lenis drives buttery momentum on the manual wheel/trackpad,
// and we layer the chat-scroll best practices on top:
//   1. Stick to bottom ONLY when the user is already near the bottom (never yank them off history).
//   2. Follow new content (and a streaming reply) via a ResizeObserver, pinned instantly so text
//      flows in without a jump.
//   3. A "scroll to latest" button appears when the user has scrolled up.
//   4. CSS scroll anchoring keeps the viewport stable when content above changes.

import { useEffect, useRef, useState, type ReactNode } from "react";
import Lenis from "lenis";
import "lenis/dist/lenis.css";
import { LuArrowDown } from "react-icons/lu";
import { AlphaAvatar } from "@/components/chat/AlphaAvatar";
import { RevealedMarkdown } from "@/components/chat/RevealedMarkdown";
import { useChatStore } from "@/store/chatStore";

const STICK_THRESHOLD = 120; // px from bottom that still counts as "at the bottom"

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
  const wrapperRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const lenisRef = useRef<Lenis | null>(null);
  const stickRef = useRef(true);
  const [showJump, setShowJump] = useState(false);

  function scrollToBottom(immediate: boolean) {
    const w = wrapperRef.current;
    if (!w || !lenisRef.current) return;
    lenisRef.current.scrollTo(w.scrollHeight, { immediate, duration: 0.5 });
  }

  // Lenis smooth scroll on this container + track whether we're stuck to the bottom.
  useEffect(() => {
    const wrapper = wrapperRef.current;
    const content = contentRef.current;
    if (!wrapper || !content) return;

    const lenis = new Lenis({ wrapper, content, lerp: 0.12, smoothWheel: true });
    lenisRef.current = lenis;

    let raf = 0;
    const loop = (t: number) => {
      lenis.raf(t);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    const onScroll = () => {
      const dist = content.scrollHeight - (wrapper.scrollTop + wrapper.clientHeight);
      stickRef.current = dist < STICK_THRESHOLD;
      setShowJump(dist > STICK_THRESHOLD * 2);
    };
    lenis.on("scroll", onScroll);

    // Follow new content (new turns + the streaming reveal) — but only while stuck to the bottom.
    const ro = new ResizeObserver(() => {
      if (stickRef.current) scrollToBottom(true);
    });
    ro.observe(content);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      lenis.destroy();
      lenisRef.current = null;
    };
  }, []);

  const hasContent = turns.length > 0 || pending;

  return (
    <div className={`relative ${className}`}>
      <div ref={wrapperRef} className="h-full overflow-y-auto scrollbar-subtle" style={{ overflowAnchor: "none" }}>
        <div ref={contentRef} className="flex flex-col gap-4 py-1">
          {!hasContent ? (
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
                    <div className={`text-[#d4d4d8] pt-0.5 ${textClass}`}>
                      <RevealedMarkdown text={t.text} />
                    </div>
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
          {/* Scroll-anchor: the only auto anchor, so growth above never jumps the view. */}
          <div style={{ overflowAnchor: "auto", height: 1 }} />
        </div>
      </div>

      {showJump && (
        <button
          onClick={() => scrollToBottom(false)}
          aria-label="Scroll to latest"
          className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex items-center justify-center w-9 h-9 rounded-full bg-[#242424] border border-[#3a3a3a] text-[#d4d4d8] shadow-lg hover:bg-[#2e2e2e] transition-colors cursor-pointer"
        >
          <LuArrowDown size={17} />
        </button>
      )}
    </div>
  );
}
