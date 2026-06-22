import { AnimatePresence, motion } from "framer-motion";
import { useRef, useState } from "react";
import { AlphaReactionSheet } from "@/components/composer/AlphaReactionSheet";
import { DropHalo } from "@/components/composer/DropHalo";
import { InstinctChip } from "@/components/composer/InstinctChip";
import { OneBox } from "@/components/composer/OneBox";
import { StrategyPicker } from "@/components/composer/StrategyPicker";
import { DenDrawer } from "@/components/den/DenDrawer";
import { ChatThread } from "@/components/chat/ChatThread";
import { api, type IntakeTurn, type StrategyName } from "@/net/api";
import { useChatStore } from "@/store/chatStore";

const INSTINCT_CHIPS = [
  { title: "The Newsroom", subtitle: "Verify claims and write articles" },
  { title: "The Meeting Room", subtitle: "Summarize recordings and decisions" },
  { title: "The Counsel", subtitle: "Review documents and flag risks" },
  { title: "The Pipeline", subtitle: "Research leads and draft outreach" },
  { title: "The Support Desk", subtitle: "Resolve tickets and draft replies" },
];

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
  const [strategy, setStrategy] = useState<StrategyName>("orchestrate");
  const [error, setError] = useState(false);
  const folderToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const {
    turns,
    pending,
    proposal,
    addUser,
    addAlpha,
    setPending,
    propose,
    clearProposal,
    bindHunt,
    dropLastAlpha,
    truncateFrom,
  } = useChatStore();
  const chatting = turns.length > 0 || pending;

  // Front-door clarify-gate: Alpha talks normally and only PROPOSES a hunt once there's a real job.
  // Nothing launches until the Packmaster confirms (see confirmSend).
  async function runIntake() {
    const convo: IntakeTurn[] = useChatStore.getState().turns.map((t) => ({
      role: t.role === "alpha" ? "assistant" : "user",
      content: t.text,
    }));
    setError(false);
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
      // Leave the thread at the user's turn and surface a real Retry, not a fake "reply".
      setError(true);
    } finally {
      setPending(false);
    }
  }

  function retry() {
    runIntake();
  }

  async function handleSend(text: string) {
    addUser(text);
    clearProposal();
    await runIntake();
  }

  // Regenerate: drop Alpha's last reply and re-answer the same prompt.
  async function handleRegenerate() {
    dropLastAlpha();
    await runIntake();
  }

  // Edit & resend: pull the prompt back into the composer and trim the thread to before it.
  function handleEdit(index: number) {
    const turn = useChatStore.getState().turns[index];
    if (!turn) return;
    setPrefill(turn.text);
    truncateFrom(index);
  }

  async function confirmSend() {
    if (!proposal) return;
    const brief = proposal.brief;
    clearProposal();
    addAlpha("On it — taking you to the plan…");
    try {
      const { hunt_id } = await api.createHunt({ input: brief, source: "typed", strategy });
      bindHunt(hunt_id);
      goToPlan(hunt_id);
    } catch {
      addAlpha("I couldn't reach the engine just now — make sure it's running and try again.");
    }
  }

  // A dropped file becomes a REAL hunt: parse (or transcribe) it, then send the pack on it.
  async function handleFileAction(action: string) {
    const file = alphaFile;
    if (!file) return;
    setAlphaFile(null);
    const t = file.type;
    if (t.startsWith("image/") || t.startsWith("video/")) {
      addAlpha("I can't read images or video yet — try a PDF, doc, spreadsheet, or audio file.");
      return;
    }
    addAlpha(`On it — ${action.toLowerCase()} from ${file.name}.`);
    try {
      const isAudio = t.startsWith("audio/");
      const parsed = isAudio ? await api.transcribe(file) : await api.parse(file);
      const text = (parsed.text || "").trim();
      if (!text) {
        addAlpha("I couldn't pull any text out of that file — tell me what's in it and I'll go.");
        return;
      }
      const task = `${action}. Source material from ${file.name}:\n\n${text}`.slice(0, 8000);
      const { hunt_id } = await api.createHunt({
        input: task,
        source: isAudio ? "spoken" : "dropped",
        strategy,
      });
      bindHunt(hunt_id);
      goToPlan(hunt_id);
    } catch {
      addAlpha("I couldn't read that file just now — try again, or just tell me what's in it.");
    }
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

  // The launch CTA — a soft, scoped suggested-action chip near the input (NN/g prompt controls),
  // not a jarring button block. Typing instead just keeps the conversation going (re-clarifies).
  const launchChip = proposal ? (
    <div className="w-[min(760px,92vw)] shrink-0 flex flex-col gap-2 mb-2.5 px-1">
      <div className="flex items-center gap-2.5">
        <span className="text-[12px] text-[#71717a]">Mode</span>
        <StrategyPicker value={strategy} onChange={setStrategy} />
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={confirmSend}
          className="group inline-flex items-center gap-2 bg-[#e6a23c]/15 text-[#e6a23c] border border-[#e6a23c]/40 rounded-full pl-3.5 pr-4 py-2 text-[13px] font-medium hover:bg-[#e6a23c]/25 transition-colors cursor-pointer"
        >
          <span className="text-[15px] leading-none">▸</span>
          Send the pack on this
        </button>
        <span className="text-[12px] text-[#71717a]">or tell me what to tweak</span>
      </div>
    </div>
  ) : null;

  // Suggested follow-ups after an Alpha answer (NN/g: reduces effort, aids discovery). Hidden while
  // a launch is pending or Alpha is mid-reply.
  const lastTurn = turns[turns.length - 1];
  const followUps =
    !pending && !proposal && lastTurn?.role === "alpha" ? (
      <div className="w-[min(760px,92vw)] shrink-0 flex flex-wrap gap-2 mb-2 px-1">
        {["Tell me more", "Make it simpler", "Turn this into a hunt"].map((f) => (
          <button
            key={f}
            onClick={() => handleSend(f)}
            className="rounded-full border border-[#2a2a2a] text-[#a1a1aa] hover:text-white hover:border-[#3a3a3a] px-3 py-1.5 text-[12px] cursor-pointer transition-colors"
          >
            {f}
          </button>
        ))}
      </div>
    ) : null;

  const errorBanner = error ? (
    <div className="w-[min(760px,92vw)] shrink-0 flex items-center gap-3 mb-2 px-1">
      <span className="text-[13px] text-[#e6a23c]">
        Couldn't reach Alpha just now — check the connection.
      </span>
      <button
        onClick={retry}
        className="rounded-lg border border-[#2a2a2a] text-[#d4d4d8] hover:text-white px-3 py-1 text-[12px] cursor-pointer"
      >
        Retry
      </button>
    </div>
  ) : null;

  // Action-oriented disclaimer placed near the input (NN/g cites this placement; Claude as the model).
  const disclaimer = (
    <p className="text-[11px] text-[#52525b] text-center mt-1.5">
      Alpha can make mistakes. Check anything important.
    </p>
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
          /* ---------- Chat surface: ChatThread is the only scroller; composer pinned below ------ */
          <main className="flex-1 min-h-0 flex flex-col items-center px-4 pb-6">
            <ChatThread
              className="w-[min(760px,92vw)] flex-1 min-h-0 py-6"
              onRegenerate={handleRegenerate}
              onEdit={handleEdit}
            />
            {followUps}
            {errorBanner}
            {launchChip}
            <div className="w-[min(760px,92vw)] shrink-0">
              {composer}
              {disclaimer}
            </div>
          </main>
        ) : (
          /* ---------- Empty state: the hero (heading + composer + chips) ---------- */
          <main className="flex-1 flex flex-col items-center justify-center px-4 pb-[8vh] overflow-auto">
            <motion.h1
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
              className="text-[24px] md:text-[36px] font-normal text-center tracking-tight m-0 mb-3"
            >
              What should the pack hunt down?
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.15 }}
              className="text-[13px] md:text-[15px] text-[#71717a] text-center m-0 mb-10 md:mb-14 max-w-[540px] px-4"
            >
              I can research, draft, review, summarize, and dig things up. Tell me what you need.
            </motion.p>

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
              {disclaimer}

              <div className="flex items-center gap-2.5 px-1 pt-0.5">
                <span className="text-[12px] text-[#71717a]">How should they hunt?</span>
                <StrategyPicker value={strategy} onChange={setStrategy} disabled={recording} />
              </div>

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
                      onAction={(action: string) => handleFileAction(action)}
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
