// A "working" indicator that describes the stages of thinking instead of a bare spinner / static
// "thinking…" (NN/g: a spinning wheel is a digital shrug). The label advances through Alpha's real
// steps (read → think → write) and then holds — it never fakes looping progress. Honors reduced-motion.

import { useEffect, useState } from "react";
import { AlphaAvatar } from "@/components/chat/AlphaAvatar";
import { useReducedMotion } from "@/lib/useReducedMotion";

const STAGES = ["Reading…", "Thinking it through…", "Writing…"];

export function ThinkingIndicator({ size = 26 }: { size?: number }) {
  const reduced = useReducedMotion();
  const [i, setI] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => setI((n) => Math.min(n + 1, STAGES.length - 1)), 1500);
    return () => clearInterval(id);
  }, [reduced]);

  return (
    <div className="flex gap-2.5 items-center" aria-label="Alpha is working">
      <AlphaAvatar size={size} />
      <span className="text-[13px] text-[#71717a] italic">{reduced ? "Working…" : STAGES[i]}</span>
    </div>
  );
}
