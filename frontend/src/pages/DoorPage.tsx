import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState } from "react";
import { AlphaReactionSheet } from "@/components/composer/AlphaReactionSheet";
import { DropHalo } from "@/components/composer/DropHalo";
import { InstinctChip } from "@/components/composer/InstinctChip";
import { OneBox } from "@/components/composer/OneBox";
import { api } from "@/net/api";

const INSTINCT_CHIPS = [
  { title: "The Newsroom", subtitle: "Verify claims and write articles" },
  { title: "The Meeting Room", subtitle: "Summarize recordings and decisions" },
  { title: "The Counsel", subtitle: "Review documents and flag risks" },
  { title: "The Pipeline", subtitle: "Research leads and draft outreach" },
  { title: "The Support Desk", subtitle: "Resolve tickets and draft replies" },
];

function mockHuntId() {
  return "hunt_" + Math.random().toString(36).slice(2, 10);
}

function goToPlan(huntId: string) {
  window.history.pushState({}, "", `/plan/${huntId}`);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function DoorPage() {
  const [droppedFiles, setDroppedFiles] = useState<File[]>([]);
  const [alphaFile, setAlphaFile] = useState<File | null>(null);
  const [prefill, setPrefill] = useState<string | undefined>();
  const [recording, setRecording] = useState(false);
  const [folderToast, setFolderToast] = useState(false);
  const folderToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showFolderToast() {
    if (folderToastTimer.current) clearTimeout(folderToastTimer.current);
    setFolderToast(true);
    folderToastTimer.current = setTimeout(() => setFolderToast(false), 3000);
  }

  function handleFilesDropped(files: File[]) {
    setDroppedFiles(files);
    if (files.length > 0) setAlphaFile(files[0]);
  }

  return (
    <DropHalo onFilesDropped={handleFilesDropped} onFolderRejected={showFolderToast}>
      <div className="fixed inset-0 bg-door-bg text-white font-sans flex flex-col overflow-auto">
        <header className="sticky top-0 z-10 px-7 py-5 bg-door-bg">
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
            className="text-base md:text-2xl font-medium tracking-wide"
          >
            Pack
          </motion.span>
        </header>

        <main className="flex-1 flex flex-col items-center justify-center px-4 pb-[8vh]">
          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
            className="text-[24px] md:text-[36px] font-normal text-center tracking-tight m-0 mb-10 md:mb-16"
          >
            What should the pack hunt down?
          </motion.h1>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1, ease: [0.2, 0.8, 0.2, 1] }}
            className="w-[min(880px,90vw)] flex flex-col gap-2"
          >
            {/* Folder rejection toast */}
            <AnimatePresence>
              {folderToast && (
                <motion.p
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.2 }}
                  className="text-[12px] text-amber-400 m-0 px-1"
                >
                  Folders can't be added — only files are supported.
                </motion.p>
              )}
            </AnimatePresence>

            <OneBox
              droppedFiles={droppedFiles}
              prefill={prefill}
              onFilesAdded={(files) => setAlphaFile(files[0])}
              onFileRemoved={(name) => {
                if (alphaFile?.name === name) setAlphaFile(null);
              }}
              onFolderRejected={showFolderToast}
              onRecordingChange={setRecording}
              onSubmit={async ({ text }) => {
                // Open a real hunt on the engine, then watch it on the hunt screen. Falls back
                // to a local id if the backend isn't reachable, so the Door still navigates.
                try {
                  const { hunt_id } = await api.createHunt({ input: text, source: "typed" });
                  goToPlan(hunt_id);
                } catch {
                  goToPlan(mockHuntId());
                }
              }}
            />

            <AnimatePresence>
              {alphaFile && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ duration: 0.2 }}
                >
                  <AlphaReactionSheet
                    file={alphaFile}
                    onDismiss={() => setAlphaFile(null)}
                    onAction={(_action: string) => {
                      setAlphaFile(null);
                      goToPlan(mockHuntId());
                    }}
                  />
                </motion.div>
              )}
            </AnimatePresence>

            {/* Chips — horizontal scroll on mobile, row on desktop */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2, ease: [0.2, 0.8, 0.2, 1] }}
              className="flex gap-3 overflow-x-auto pb-1 scrollbar-none"
            >
              {INSTINCT_CHIPS.map((chip) => (
                <InstinctChip
                  key={chip.title}
                  title={chip.title}
                  subtitle={chip.subtitle}
                  onClick={() => setPrefill(chip.title)}
                  disabled={recording}
                />
              ))}
            </motion.div>
          </motion.div>
        </main>
      </div>
    </DropHalo>
  );
}
