// The Den — a slide-in drawer of Past Hunts + Saved Instincts (Doc 02). Both come from the engine
// (GET /hunts, GET /instincts). New-chat, keyword search, and recency grouping are client-side.
// (Rename / delete / archive / pin need backend endpoints — flagged, not faked.)

import { useEffect, useMemo, useState } from "react";
import { LuPanelLeft, LuX, LuSearch, LuPlus } from "react-icons/lu";
import { api, type HuntListItem, type Instinct } from "@/net/api";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const DAY = 86_400_000;
const BUCKETS: { label: string; max: number }[] = [
  { label: "Today", max: DAY },
  { label: "Yesterday", max: 2 * DAY },
  { label: "Previous 7 days", max: 7 * DAY },
  { label: "Older", max: Infinity },
];

function groupByRecency(hunts: HuntListItem[]): { label: string; items: HuntListItem[] }[] {
  const now = Date.now();
  return BUCKETS.map((b, i) => {
    const min = i === 0 ? 0 : BUCKETS[i - 1].max;
    return {
      label: b.label,
      items: hunts.filter((h) => {
        const age = now - new Date(h.created_at).getTime();
        return age >= min && age < b.max;
      }),
    };
  }).filter((g) => g.items.length > 0);
}

export function DenDrawer() {
  const [open, setOpen] = useState(false);
  const [hunts, setHunts] = useState<HuntListItem[]>([]);
  const [instincts, setInstincts] = useState<Instinct[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!open) return;
    Promise.allSettled([api.listHunts(), api.listInstincts()]).then(([h, i]) => {
      if (h.status === "fulfilled") setHunts(h.value.hunts);
      if (i.status === "fulfilled") setInstincts(i.value.instincts);
      setLoaded(true);
    });
  }, [open]);

  const ql = q.trim().toLowerCase();
  const filteredHunts = useMemo(
    () => (ql ? hunts.filter((h) => h.title.toLowerCase().includes(ql)) : hunts),
    [hunts, ql],
  );
  const filteredInstincts = useMemo(
    () => (ql ? instincts.filter((i) => i.label.toLowerCase().includes(ql)) : instincts),
    [instincts, ql],
  );
  const huntGroups = ql ? [{ label: "Results", items: filteredHunts }] : groupByRecency(filteredHunts);

  function openHunt(id: string) {
    setOpen(false);
    goTo(`/hunt/${id}`);
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="absolute top-5 right-5 z-20 p-2 text-[#A3A3A3] hover:text-white bg-transparent border-none cursor-pointer"
        title="Past hunts"
      >
        <LuPanelLeft size={20} />
      </button>

      {open && (
        <div className="absolute inset-0 z-30 flex">
          <div className="flex-1 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="w-[320px] h-full bg-[#1A1A1A] border-l border-[#2a2a2a] flex flex-col">
            <header className="px-5 py-4 border-b border-[#2a2a2a] flex items-center justify-between">
              <h2 className="text-[14px] font-medium m-0">The Den</h2>
              <button className="text-[#A3A3A3] hover:text-white" onClick={() => setOpen(false)}>
                <LuX size={18} />
              </button>
            </header>

            <div className="px-4 pt-3 pb-2 flex flex-col gap-2 border-b border-[#2a2a2a]">
              <button
                onClick={() => {
                  setOpen(false);
                  goTo("/");
                }}
                className="flex items-center gap-2 rounded-lg bg-[#242424] hover:bg-[#2e2e2e] px-3 py-2 text-[13px] text-white cursor-pointer border-none"
              >
                <LuPlus size={15} /> New hunt
              </button>
              <div className="flex items-center gap-2 rounded-lg bg-[#0F0F0F] border border-[#2a2a2a] px-2.5 py-1.5">
                <LuSearch size={14} className="text-[#71717a] shrink-0" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search hunts…"
                  className="flex-1 bg-transparent border-none outline-none text-[13px] text-white placeholder:text-[#71717a]"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6 scrollbar-subtle">
              {huntGroups.length === 0 ? (
                <Empty text={loaded ? (ql ? "No hunts match." : "No hunts yet — send the pack.") : "Loading…"} />
              ) : (
                huntGroups.map((g) => (
                  <Section key={g.label} title={g.label}>
                    {g.items.map((h) => (
                      <Row
                        key={h.hunt_id}
                        title={h.title}
                        sub={`${h.state} · ${new Date(h.created_at).toLocaleDateString()}`}
                        onClick={() => openHunt(h.hunt_id)}
                      />
                    ))}
                  </Section>
                ))
              )}

              <Section title="Saved instincts">
                {filteredInstincts.length === 0 ? (
                  <Empty text={loaded ? (ql ? "No instincts match." : "No saved instincts.") : "Loading…"} />
                ) : (
                  filteredInstincts.map((i) => (
                    <Row
                      key={i.instinct_id}
                      title={i.label}
                      sub="instinct"
                      onClick={() =>
                        api
                          .createHunt({ instinct_id: i.instinct_id, source: "typed" })
                          .then(({ hunt_id }) => {
                            setOpen(false);
                            goTo(`/hunt/${hunt_id}/plan`);
                          })
                          .catch(() => {})
                      }
                    />
                  ))
                )}
              </Section>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-[11px] uppercase tracking-wide text-[#71717a] m-0">{title}</h3>
      {children}
    </div>
  );
}

function Row({ title, sub, onClick }: { title: string; sub: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-left bg-[#0F0F0F] border border-[#2a2a2a] rounded-lg px-3 py-2.5 hover:border-[#404040] cursor-pointer w-full"
    >
      <div className="text-[13px] text-white truncate">{title}</div>
      <div className="text-[11px] text-[#71717a] mt-0.5">{sub}</div>
    </button>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="text-[12px] text-[#52525b] m-0">{text}</p>;
}
