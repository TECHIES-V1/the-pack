// Alpha's reply, revealed with the gentle typed-out feel but rendered as Markdown (lists, bold,
// etc.). The reveal is bounded (~50 steps) so even a long, formatted reply lands quickly and
// smoothly. Partial Markdown mid-reveal is fine — it resolves as the text completes (like ChatGPT).

import { useEffect, useState } from "react";
import { MarkdownReply } from "./MarkdownReply";
import { useReducedMotion } from "@/lib/useReducedMotion";

export function RevealedMarkdown({ text }: { text: string }) {
  const [shown, setShown] = useState(0);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) {
      setShown(text.length); // no typewriter when the user asked for reduced motion
      return;
    }
    setShown(0);
    if (!text) return;
    const step = Math.max(2, Math.ceil(text.length / 50));
    const id = setInterval(() => {
      setShown((n) => {
        const next = Math.min(n + step, text.length);
        if (next >= text.length) clearInterval(id);
        return next;
      });
    }, 22);
    return () => clearInterval(id);
  }, [text, reduced]);

  return <MarkdownReply text={text.slice(0, shown)} />;
}
