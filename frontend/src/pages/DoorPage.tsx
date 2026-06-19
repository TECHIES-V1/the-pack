import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { AlphaReactionSheet } from "@/components/composer/AlphaReactionSheet";
import { DropHalo } from "@/components/composer/DropHalo";
import { InstinctChip } from "@/components/composer/InstinctChip";
import { OneBox } from "@/components/composer/OneBox";
import { DenDrawer } from "@/components/den/DenDrawer";
import { AlphaAvatar } from "@/components/chat/AlphaAvatar";
import { TypeOut } from "@/components/chat/TypeOut";
import { api, type IntakeTurn } from "@/net/api";
import { useChatStore } from "@/store/chatStore";

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
  window.history.pushState({}, "", `/hunt/${huntId}/plan`);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function DoorPage() {
  const [droppedFiles, setDroppedFiles] = useState<File[]>([]);
  const [alphaFile, setAlphaFile] = useState<File | null>(null);
  const [prefill, setPrefill] = useState<string | undefined>();
  const [recording, setRecording] = useState(false);
  const [folderToast, setFolderToast] = useState(false);
  const folderToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { turns, pending, proposal, addUser, addAlpha, setPending, propose, clearProposal, bindHunt } =
    useChatStore();
  const chatting = turns.length > 0 || pending;

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, pending, proposal]);

  // Front-door clarify-gate: Alpha reads the conversation and only PROPOSES a hunt once there's a
  // real, actionable task. Nothing launches until the Packmaster confirms (see confirmSend).
  async function handleSend(text: string) {
    const convo: IntakeTurn[] = [...turns, { role: "user" as const, text }].map((t) => ({
      role: t.role === "alpha" ? "assistant" : "user",
      content: t.text,
    }));
    addUser(text);
    clearProposal();
    setPending(true);
    try {
      const { reply, ready, brief } = await api.intake(convo);
      if (ready) {
        propose(brief);
        addAlpha(reply?.trim() ? reply : `Got it — here's the hunt: "${brief}"`);
      } else {
        addAlpha(reply);
      }
    } catch {
      addAlpha("I couldn't reach you just now — try me again.");
    } finally {
      setPending(false);
    }
  }

  async function confirmSend() {
    if (!proposal) return;
    const brief = proposal.brief;
    clearProposal();
    try {
      const { hunt_id } = await api.createHunt({ input: brief, source: "typed" });
      bindHunt(hunt_id);
      goToPlan(hunt_id);
    } catch {
      goToPlan(mockHuntId());
    }
  }

  function adjust() {
    clearProposal();
    addAlpha("No problem — what should I change?");
  }

  function showFolderToast() {
    if (folderToastTimer.current) clearTimeout(folderToastTimer.current);
    setFolderToast(true);
    folderToastTimer.current = setTimeout(() => setFolderToast(false), 3000);
  }

  function handleFilesDropped(files: File[]) {
    setDroppedFiles(files);
    if (files.length > 0) setAlphaFile(files[0]);
  }

  const composer = (
    <OneBox
      droppedFiles={droppedFiles}
      prefill={prefill}
      placeholder={chatting ? "Talk to Alpha…" : "What should the pack hunt down?"}
      onFilesAdded={(files) => setAlphaFile(files[0])}
      onFileRemoved={(name) => {
        if (alphaFile?.name === name) setAlphaFile(null);
      }}
      onFolderRejected={showFolderToast}
      onRecordingChange={setRecording}
      onSubmit={({ text }) => handleSend(text)}
    />
  );

  return (
    <DropHalo onFilesDropped={handleFilesDropped} onFolderRejected={showFolderToast}>
      <div className="fixed inset-0 bg-door-bg text-white font-sans flex flex-col overflow-hidden">
        <DenDrawer />
        <header className="shrink-0 px-7 py-5 bg-door-bg">
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
            className="text-base md:text-2xl font-medium tracking-wide"
          >
            Pack
          </motion.span>
        </header>

        {chatting ? (
          /* ---------- Chat surface: transcript fills the space, composer pinned below ---------- */
          <main className="flex-1 min-h-0 flex flex-col items-center px-4 pb-6">
            <div className="w-[min(760px,92vw)] flex-1 min-h-0 overflow-y-auto scrollbar-subtle flex flex-col gap-4 py-6">
              {turns.map((t, i) =>
                t.role === "user" ? (
                  <div
                    key={i}
                    className="bg-[#242424] rounded-2xl px-4 py-2.5 text-[14px] text-[#e4e4e7] self-end max-w-[80%]"
                  >
                    {t.text}
                  </div>
                ) : (
                  <div key={i} className="flex gap-2.5 items-start max-w-[88%]">
                    <AlphaAvatar />
                    <p className="text-[14px] leading-relaxed text-[#d4d4d8] m-0 pt-0.5">
                      <TypeOut text={t.text} />
                    </p>
                  </div>
                ),
              )}

              {pending && (
                <div className="flex gap-2.5 items-center">
                  <AlphaAvatar />
                  <span className="text-[13px] text-[#71717a] italic">Alpha is thinking…</span>
                </div>
              )}

              {/* The confirm beat — nothing launches until the Packmaster clicks */}
              {proposal && (
                <div className="flex gap-2.5 self-start ml-[34px]">
                  <button
                    onClick={confirmSend}
                    className="bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium hover:bg-white/90 cursor-pointer border-none"
                  >
                    Send the pack →
                  </button>
                  <button
                    onClick={adjust}
                    className="bg-transparent text-[#a1a1aa] border border-[#2a2a2a] rounded-lg px-4 py-2 text-[13px] cursor-pointer hover:text-white"
                  >
                    Adjust
                  </button>
                </div>
              )}

              <div ref={bottomRef} />
            </div>

            <div className="w-[min(760px,92vw)] shrink-0">{composer}</div>
          </main>
        ) : (
          /* ---------- Empty state: the hero (heading + composer + chips) ---------- */
          <main className="flex-1 flex flex-col items-center justify-center px-4 pb-[8vh] overflow-auto">
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

              {composer}

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
        )}
      </div>
    </DropHalo>
  );
}
