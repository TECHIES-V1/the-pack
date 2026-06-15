import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";

interface DropHaloProps {
  children: React.ReactNode;
  onFilesDropped?: (files: File[]) => void;
  onFolderRejected?: () => void;
}

export function DropHalo({ children, onFilesDropped, onFolderRejected }: DropHaloProps) {
  const [active, setActive] = useState(false);
  const counter = useRef(0);

  const onDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer?.types.includes("Files")) {
      counter.current += 1;
      setActive(true);
    }
  }, []);

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
  }, []);

  const onDragLeave = useCallback(() => {
    counter.current -= 1;
    if (counter.current === 0) setActive(false);
  }, []);

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      counter.current = 0;
      setActive(false);
      const items = Array.from(e.dataTransfer?.items ?? []);
      const files: File[] = [];
      let hadFolder = false;
      for (const item of items) {
        const entry = item.webkitGetAsEntry?.();
        if (entry && !entry.isFile) { hadFolder = true; continue; }
        const file = item.getAsFile();
        if (file) files.push(file);
      }
      if (hadFolder) onFolderRejected?.();
      if (files.length > 0) onFilesDropped?.(files);
    },
    [onFilesDropped, onFolderRejected]
  );

  useEffect(() => {
    window.addEventListener("dragenter", onDragEnter);
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("dragleave", onDragLeave);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragenter", onDragEnter);
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("dragleave", onDragLeave);
      window.removeEventListener("drop", onDrop);
    };
  }, [onDragEnter, onDragOver, onDragLeave, onDrop]);

  return (
    <div className="relative w-full h-full">
      {children}

      <AnimatePresence>
        {active && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 pointer-events-auto flex flex-col items-center justify-center gap-4 bg-door-bg/85"
          >
            {/* File icon */}
            <svg width="56" height="56" viewBox="0 0 64 64" fill="none" className="text-[#aaa]">
              <path
                d="M16 8h24l12 12v36a4 4 0 01-4 4H16a4 4 0 01-4-4V12a4 4 0 014-4z"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M40 8v12h12"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>

            <p className="text-white text-2xl font-medium tracking-tight m-0">
              Drop files here to add to chat
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
