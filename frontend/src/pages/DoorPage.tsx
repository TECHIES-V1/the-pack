import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { LuSettings, LuLayoutDashboard } from "react-icons/lu";
import { DropHalo } from "@/components/composer/DropHalo";
import { InstinctChip } from "@/components/composer/InstinctChip";
import { OneBox } from "@/components/composer/OneBox";
import { StrategyPicker } from "@/components/composer/StrategyPicker";
import { DenDrawer } from "@/components/den/DenDrawer";
import { ChatThread } from "@/components/chat/ChatThread";
import { api, streamSSE, ApiError, type StrategyName, type HuntListItem, type Instinct } from "@/net/api";
import { useChatStore } from "@/store/chatStore";
import { useUiStore } from "@/store/uiStore";
import { withCustomInstructions } from "@/store/settingsStore";

const SUGGESTED_PROMPTS = [
  "Research the top AI coding tools in 2025 and write a brief",
  "Fact-check and summarize the latest news on quantum computing",
  "Compare the best project management tools for a small team",
];

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

// Told to Alpha during intake so he can acknowledge the chosen approach when proposing a hunt.
const STRATEGY_NOTE: Record<StrategyName, string> = {
  orchestrate: "If a hunt launches, it will use dynamic orchestration — the pack adapts as it learns.",
  deep_dive: "If a hunt launches, it will use iterative deep research — search, find gaps, search again.",
  critique: "If a hunt launches, it will use plan-execute-critique — the Sentinel challenges weak claims.",
};

function goToPlan(huntId: string) {
  window.history.pushState({}, "", `/hunt/${huntId}/plan`);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function DoorPage() {
  const [droppedFiles, setDroppedFiles] = useState<File[]>([]);
  // A file attached in the chat: parsed to text and fed to Alpha as context (not a forced hunt).
  const [attached, setAttached] = useState<{ name: string; text: string } | null>(null);
  const [prefill, setPrefill] = useState<string | undefined>();
  const [recording, setRecording] = useState(false);
  const [folderToast, setFolderToast] = useState(false);
  const [strategy, setStrategy] = useState<StrategyName>("orchestrate");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeHunt, setActiveHunt] = useState<HuntListItem | null>(null);
  const [instincts, setInstincts] = useState<Instinct[]>([]);
  const folderToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { setSettingsOpen, setDenOpen } = useUiStore();

  const ACTIVE_STATES = new Set(["plan_ready", "hunting", "holding", "standoff", "finishing"]);

  useEffect(() => {
    api.listHunts().then(({ hunts }) => {
      const found = hunts.find((h) => ACTIVE_STATES.has(h.state)) ?? null;
      setActiveHunt(found);
    }).catch(() => {});
    // The Packmaster's saved instincts — shown on the hero so they're reusable from the front
    // door, not buried in the Den.
    api.listInstincts().then(({ instincts }) => setInstincts(instincts)).catch(() => {});
    // Auto-open Den when arriving from "← Home" on the canvas
    if (new URLSearchParams(window.location.search).get("den") === "open") {
      setDenOpen(true);
    }
  }, []);

  const {
    turns,
    pending,
    proposal,
    addUser,
    addAlpha,
    setAbortFn,
    setPending,
    propose,
    clearProposal,
    bindHunt,
    dropLastAlpha,
    truncateFrom,
  } = useChatStore();
  const chatting = turns.length > 0 || pending;

  // A fresh conversation (New hunt / cleared) drops any attached file.
  useEffect(() => {
    if (turns.length === 0) setAttached(null);
  }, [turns.length]);

  // Front-door clarify-gate: Alpha talks normally and only PROPOSES a hunt once there's a real job.
  // Nothing launches until the Packmaster confirms (see confirmSend).
  async function runIntake() {
    type Msg = { role: "system" | "user" | "assistant"; content: string };
    const base: Msg[] = useChatStore.getState().turns.map((t) => ({
      role: t.role === "alpha" ? "assistant" : "user",
      content: t.text,
    }));
    // Context Alpha needs but the user shouldn't see as chat turns: the chosen approach + any file.
    const ctx: Msg[] = [{ role: "system", content: STRATEGY_NOTE[strategy] }];
    if (attached) {
      ctx.push({ role: "user", content: `Attached file "${attached.name}":\n\n${attached.text}` });
    }
    const convo = withCustomInstructions<Msg>([...ctx, ...base]);
    setErrorMsg(null);
    setPending(true);
    const ctrl = new AbortController();
    setAbortFn(() => ctrl.abort());
    try {
      let streamError: string | null = null;
      // Intake streams the model's RAW JSON ({"reply":…,"ready":…}) as token events — NEVER render
      // those. The pending indicator covers the wait; only the parsed `done` reply is shown.
      for await (const event of streamSSE("/hunts/intake/stream", { messages: convo }, ctrl.signal)) {
        if (event.type === "error") { streamError = ERROR_MESSAGES[(event.kind as string) ?? "unknown"] ?? ERROR_MESSAGES.unknown; break; }
        if (event.type === "done") {
          const reply = (event.reply as string) ?? "";
          const ready = Boolean(event.ready);
          const brief = (event.brief as string) ?? "";
          if (ready) propose(brief);
          addAlpha(ready && !reply.trim() ? `Got it — here's the hunt: "${brief}"` : reply);
        }
      }
      if (streamError) setErrorMsg(streamError);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? ERROR_MESSAGES[err.kind] : ERROR_MESSAGES.unknown);
    } finally {
      setAbortFn(null);
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

  // A file attached in the chat is parsed and held as CONTEXT — Alpha can discuss it; a hunt only
  // launches when there's a real task (the normal clarify-gate). It is NOT a forced hunt.
  async function parseAttachment(file: File) {
    const t = file.type;
    if (t.startsWith("image/") || t.startsWith("video/")) {
      addAlpha("I can't read images or video yet — try a PDF, doc, spreadsheet, or audio file.");
      return;
    }
    try {
      const parsed = t.startsWith("audio/") ? await api.transcribe(file) : await api.parse(file);
      const text = (parsed.text || "").trim();
      if (!text) {
        addAlpha(`I couldn't pull any text out of ${file.name} — tell me what's in it.`);
        return;
      }
      setAttached({ name: file.name, text: text.slice(0, 8000) });
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
    setDroppedFiles(files); // flows to OneBox → onFilesAdded → parseAttachment
  }

  const composer = (
    <OneBox
      droppedFiles={droppedFiles}
      prefill={prefill}
      hideMode
      placeholder={chatting ? "Talk to Alpha…" : "What should the pack hunt down?"}
      onFilesAdded={(files) => files[0] && parseAttachment(files[0])}
      onFileRemoved={(name) => {
        if (attached?.name === name) setAttached(null);
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

  // The active attachment — Alpha keeps reading it through the conversation until it's removed.
  const attachmentChip = attached ? (
    <div className="w-[min(760px,92vw)] shrink-0 flex items-center gap-2 mb-2 px-1">
      <span className="inline-flex items-center gap-1.5 rounded-full bg-[#242424] border border-[#2a2a2a] px-3 py-1 text-[12px] text-[#d4d4d8]">
        <span aria-hidden>📎</span>
        <span className="max-w-[240px] truncate">{attached.name}</span>
        <button
          onClick={() => setAttached(null)}
          className="text-[#71717a] hover:text-white bg-transparent border-none cursor-pointer leading-none text-[14px]"
          aria-label="Remove attachment"
        >
          ×
        </button>
      </span>
      <span className="text-[11px] text-[#71717a]">Alpha will read this in the conversation.</span>
    </div>
  ) : null;

  return (
    <DropHalo onFilesDropped={handleFilesDropped} onFolderRejected={showFolderToast}>
      <div className="fixed inset-0 bg-door-bg text-white font-sans flex flex-col overflow-hidden">
        <DenDrawer />
        <button
          onClick={() => setSettingsOpen(true)}
          className="absolute top-5 right-14 z-20 p-2 text-[#A3A3A3] hover:text-white bg-transparent border-none cursor-pointer"
          title="Settings (⌘,)"
          aria-label="Settings"
        >
          <LuSettings size={19} />
        </button>
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
            {attachmentChip}
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

              {attachmentChip}
              {composer}
              {disclaimer}

              <div className="flex items-center gap-2.5 px-1 pt-0.5">
                <span className="text-[12px] text-[#71717a]">How should they hunt?</span>
                <StrategyPicker value={strategy} onChange={setStrategy} disabled={recording} />
              </div>

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

              {instincts.length > 0 && (
                <div className="flex flex-col gap-1.5 pt-0.5">
                  <span className="text-[11px] uppercase tracking-wide text-[#52525b] px-1">
                    Your saved instincts
                  </span>
                  <div className="flex flex-wrap gap-2 px-1">
                    {instincts.map((i) => (
                      <button
                        key={i.instinct_id}
                        disabled={recording}
                        onClick={() =>
                          api
                            .createHunt({ instinct_id: i.instinct_id, source: "typed" })
                            .then(({ hunt_id }) => {
                              bindHunt(hunt_id);
                              goToPlan(hunt_id);
                            })
                            .catch(() => {})
                        }
                        className="rounded-full border border-[#2a2a2a] text-[#a1a1aa] hover:text-white hover:border-[#3a3a3a] px-3 py-1.5 text-[12px] cursor-pointer transition-colors disabled:opacity-50"
                      >
                        {i.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.3 }}
                className="flex flex-col gap-1.5 pt-1"
              >
                {SUGGESTED_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => handleSend(p)}
                    className="text-left text-[12px] text-[#52525b] hover:text-[#a1a1aa] transition-colors cursor-pointer bg-transparent border-none p-0 px-1"
                  >
                    {p} →
                  </button>
                ))}
              </motion.div>
            </motion.div>
          </main>
        )}
      </div>
    </DropHalo>
  );
}
