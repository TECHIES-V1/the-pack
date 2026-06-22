import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { LuSettings, LuLayoutDashboard } from "react-icons/lu";
import { AlphaReactionSheet } from "@/components/composer/AlphaReactionSheet";
import { DropHalo } from "@/components/composer/DropHalo";
import { InstinctChip } from "@/components/composer/InstinctChip";
import { OneBox } from "@/components/composer/OneBox";
import { StrategyPicker } from "@/components/composer/StrategyPicker";
import { DenDrawer } from "@/components/den/DenDrawer";
import { ChatThread } from "@/components/chat/ChatThread";
import { SettingsModal } from "@/components/settings/SettingsModal";
import { api, streamSSE, ApiError, type IntakeTurn, type StrategyName, type HuntListItem } from "@/net/api";
import { useChatStore } from "@/store/chatStore";
import { withCustomInstructions } from "@/store/settingsStore";

const INSTINCT_CHIPS = [
  { title: "The Newsroom", subtitle: "Verify claims and write articles" },
  { title: "The Meeting Room", subtitle: "Summarize recordings and decisions" },
  { title: "The Counsel", subtitle: "Review documents and flag risks" },
  { title: "The Pipeline", subtitle: "Research leads and draft outreach" },
  { title: "The Support Desk", subtitle: "Resolve tickets and draft replies" },
];

const ERROR_MESSAGES: Record<string, string> = {
  engine_down: "The engine isn't running — start it with `uvicorn app.main:app`.",
  rate_limit: "Alpha is rate-limited — give it ~30 seconds and try again.",
  timeout: "That took too long — the pack might be overloaded.",
  content_filter: "That topic was filtered — try rephrasing.",
  context_exceeded: "This conversation is too long — start a new one.",
  unknown: "Couldn't reach Alpha — check the connection and try again.",
};

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
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeHunt, setActiveHunt] = useState<HuntListItem | null>(null);
  const folderToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const ACTIVE_STATES = new Set(["plan_ready", "hunting", "holding", "standoff", "finishing"]);

  useEffect(() => {
    api.listHunts().then(({ hunts }) => {
      const found = hunts.find((h) => ACTIVE_STATES.has(h.state)) ?? null;
      setActiveHunt(found);
    }).catch(() => {});
  }, []);

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
    const convo: IntakeTurn[] = withCustomInstructions(
      useChatStore.getState().turns.map((t) => ({
        role: t.role === "alpha" ? "assistant" : "user",
        content: t.text,
      })),
    );
    setErrorMsg(null);
    setPending(true);
    try {
      // Intake response is JSON so we only care about the `done` event (skip raw JSON token events).
      for await (const event of streamSSE("/hunts/intake/stream", { messages: convo })) {
        if (event.type === "error") {
          setErrorMsg(ERROR_MESSAGES[(event.kind as string) ?? "unknown"] ?? ERROR_MESSAGES.unknown);
          break;
        }
        if (event.type === "done") {
          const reply = (event.reply as string) ?? "";
          const ready = Boolean(event.ready);
          const brief = (event.brief as string) ?? "";
          if (ready) {
            propose(brief);
            addAlpha(reply.trim() ? reply : `Got it — here's the hunt: "${brief}"`);
          } else {
            addAlpha(reply);
          }
        }
      }
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? ERROR_MESSAGES[err.kind] : ERROR_MESSAGES.unknown);
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
      // Seed the Door conversation into the hunt so it persists (sequential to keep seq order).
      const seed = useChatStore.getState().turns;
      void (async () => {
        for (const t of seed) await api.saveMessage(hunt_id, t.role, t.text).catch(() => {});
      })();
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

  const errorBanner = errorMsg ? (
    <div className="w-[min(760px,92vw)] shrink-0 flex items-center gap-3 mb-2 px-1">
      <span className="text-[13px] text-[#e6a23c]">{errorMsg}</span>
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
        <button
          onClick={() => setSettingsOpen(true)}
          className="absolute top-5 right-14 z-20 p-2 text-[#A3A3A3] hover:text-white bg-transparent border-none cursor-pointer"
          title="Settings"
          aria-label="Settings"
        >
          <LuSettings size={19} />
        </button>
        {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
        <header className="shrink-0 px-7 py-5 bg-door-bg flex items-center justify-between">
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
            className="text-base md:text-2xl font-medium tracking-wide"
          >
            Pack
          </motion.span>

          {activeHunt && (
            <motion.button
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              onClick={() => goToPlan(activeHunt.hunt_id)}
              className="flex items-center gap-2 rounded-lg border border-[#3fb27f]/40 bg-[#3fb27f]/10 text-[#3fb27f] px-3 py-1.5 text-[12px] hover:bg-[#3fb27f]/20 transition-colors cursor-pointer mr-20"
            >
              <LuLayoutDashboard size={13} />
              <span className="max-w-[180px] truncate">{activeHunt.title}</span>
              <span className="text-[#3fb27f]/60">→</span>
            </motion.button>
          )}
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
