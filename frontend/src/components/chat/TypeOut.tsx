// A gentle typewriter reveal for Alpha's replies — so they come out like he's talking, not as a
// sudden wall of text. The reveal is bounded (~90 ticks) so a long reply lands in ~1.5s, not slowly.

import { useEffect, useState } from "react";

export function TypeOut({ text }: { text: string }) {
  const [shown, setShown] = useState(0);

  useEffect(() => {
    setShown(0);
    if (!text) return;
    const step = Math.max(1, Math.ceil(text.length / 90));
    const id = setInterval(() => {
      setShown((n) => {
        const next = Math.min(n + step, text.length);
        if (next >= text.length) clearInterval(id);
        return next;
      });
    }, 16);
    return () => clearInterval(id);
  }, [text]);

  return <span>{text.slice(0, shown)}</span>;
}
