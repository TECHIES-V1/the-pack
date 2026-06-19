// The Den — a slide-in drawer of Past Hunts + Saved Instincts (Doc 02). Both come from the
// engine: GET /hunts and GET /instincts. Empty state when the pack hasn't hunted yet.

import { useEffect, useState } from "react";
import { LuPanelLeft, LuX } from "react-icons/lu";
import { api, type HuntListItem, type Instinct } from "@/net/api";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function DenDrawer() {
  const [open, setOpen] = useState(false);
  const [hunts, setHunts] = useState<HuntListItem[]>([]);
  const [instincts, setInstincts] = useState<Instinct[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!open) return;
    Promise.allSettled([api.listHunts(), api.listInstincts()]).then(([h, i]) => {
      if (h.status === "fulfilled") setHunts(h.value.hunts);
      if (i.status === "fulfilled") setInstincts(i.value.instincts);
      setLoaded(true);
    });
  }, [open]);

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

            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6 scrollbar-subtle">
              <Section title="Past hunts">
                {hunts.length === 0 ? (
                  <Empty text={loaded ? "No hunts yet — send the pack." : "Loading…"} />
                ) : (
                  hunts.map((h) => (
                    <Row
                      key={h.hunt_id}
                      title={h.title}
                      sub={`${h.state} · ${new Date(h.created_at).toLocaleDateString()}`}
                      onClick={() => {
                        setOpen(false);
                        goTo(`/plan/${h.hunt_id}`);
                      }}
                    />
                  ))
                )}
              </Section>

              <Section title="Saved instincts">
                {instincts.length === 0 ? (
                  <Empty text={loaded ? "No saved instincts." : "Loading…"} />
                ) : (
                  instincts.map((i) => <Row key={i.instinct_id} title={i.label} sub="instinct" />)
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
