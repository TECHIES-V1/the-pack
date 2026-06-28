// Notifications (S — Doc 02) — derived from hunt states, no separate store: a hunt that finished is
// "done", one waiting on you (a Hold) or that failed is "needs you". Clicking routes into the hunt.

import { useCallback, useEffect, useState } from "react";
import { LuArrowLeft, LuCircleCheck, LuTriangleAlert, LuRefreshCw } from "react-icons/lu";
import { api, type HuntListItem } from "@/net/api";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const NEEDS_YOU = new Set(["holding", "failed", "halted_boundary"]);
const DONE = new Set(["returned"]);

const NEEDS_REASON: Record<string, string> = {
  holding: "Waiting on your call",
  failed: "This one didn't come together",
  halted_boundary: "Paused at your budget cap",
};

export function NotificationsPage() {
  const [hunts, setHunts] = useState<HuntListItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(() => {
    api
      .listHunts()
      .then((r) => setHunts(r.hunts))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  // Refresh on mount and whenever the tab regains focus (a hunt may have finished elsewhere).
  useEffect(() => {
    load();
    window.addEventListener("focus", load);
    return () => window.removeEventListener("focus", load);
  }, [load]);

  const needsYou = hunts.filter((h) => NEEDS_YOU.has(h.state));
  const done = hunts.filter((h) => DONE.has(h.state));

  return (
    <div className="min-h-screen bg-door-bg text-white font-sans">
      <header className="flex items-center gap-3 px-6 py-4 border-b border-[#2a2a2a]">
        <button
          onClick={() => goTo("/")}
          className="p-2 text-[#a1a1aa] hover:text-white bg-transparent border-none cursor-pointer"
          title="Home"
        >
          <LuArrowLeft size={18} />
        </button>
        <h1 className="text-[18px] font-medium m-0">Notifications</h1>
        <button
          onClick={load}
          title="Refresh"
          className="ml-auto p-2 text-[#a1a1aa] hover:text-white bg-transparent border-none cursor-pointer"
        >
          <LuRefreshCw size={15} />
        </button>
      </header>

      <div className="max-w-[680px] mx-auto px-6 py-8 flex flex-col gap-8">
        <Group title="Needs you" empty={loaded && needsYou.length === 0 ? "Nothing needs you." : ""}>
          {needsYou.map((h) => (
            <Item
              key={h.hunt_id}
              title={h.title}
              sub={NEEDS_REASON[h.state] ?? "Needs you"}
              tone="warn"
              onClick={() => goTo(`/hunt/${h.hunt_id}`)}
            />
          ))}
        </Group>

        <Group title="Done" empty={loaded && done.length === 0 ? "No finished hunts yet." : ""}>
          {done.map((h) => (
            <Item
              key={h.hunt_id}
              title={h.title}
              sub="Brief ready"
              tone="ok"
              onClick={() => goTo(`/hunt/${h.hunt_id}`)}
            />
          ))}
        </Group>
      </div>
    </div>
  );
}

function Group({ title, empty, children }: { title: string; empty: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-[11px] uppercase tracking-wide text-[#71717a] m-0">{title}</h2>
      {empty ? <p className="text-[13px] text-[#52525b] m-0">{empty}</p> : children}
    </section>
  );
}

function Item({
  title,
  sub,
  tone,
  onClick,
}: {
  title: string;
  sub: string;
  tone: "ok" | "warn";
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="text-left flex items-center gap-3 bg-[#141414] border border-[#2a2a2a] rounded-xl px-4 py-3 hover:border-[#404040] cursor-pointer w-full"
    >
      {tone === "ok" ? (
        <LuCircleCheck size={18} className="text-[#3fb27f] shrink-0" />
      ) : (
        <LuTriangleAlert size={18} className="text-[#e6a23c] shrink-0" />
      )}
      <div className="min-w-0">
        <div className="text-[13.5px] text-white truncate">{title}</div>
        <div className="text-[12px] text-[#a1a1aa]">{sub}</div>
      </div>
    </button>
  );
}
