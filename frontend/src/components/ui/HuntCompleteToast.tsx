import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useHuntStore } from "@/store/huntStore";
import { useChatStore } from "@/store/chatStore";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function HuntCompleteToast() {
  const state = useHuntStore((s) => s.view.state);
  const huntId = useChatStore((s) => s.huntId);
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (state === "returned" && window.location.pathname === "/" && !dismissed) {
      setVisible(true);
      const t = setTimeout(() => setVisible(false), 8000);
      return () => clearTimeout(t);
    }
  }, [state, dismissed]);

  function open() {
    setVisible(false);
    setDismissed(true);
    if (huntId) goTo(`/hunt/${huntId}`);
  }

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 16 }}
          transition={{ duration: 0.25 }}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-[#1A1A1A] border border-[#3fb27f]/40 rounded-xl px-4 py-3 shadow-xl"
        >
          <span className="w-2 h-2 rounded-full bg-[#3fb27f] shrink-0" />
          <span className="text-[13px] text-white">Your hunt is ready</span>
          <button
            onClick={open}
            className="text-[13px] text-[#3fb27f] font-medium hover:underline cursor-pointer border-none bg-transparent p-0"
          >
            Open brief →
          </button>
          <button
            onClick={() => { setVisible(false); setDismissed(true); }}
            className="text-[#71717a] hover:text-white text-[12px] cursor-pointer border-none bg-transparent p-0 ml-1"
          >
            ✕
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
