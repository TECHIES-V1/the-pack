// The Den — a slide-in drawer of Past Hunts + Saved Instincts (Doc 02). Both come from the engine
// (GET /hunts, GET /instincts). New-chat, keyword search, and recency grouping are client-side.
// (Rename / delete / archive / pin need backend endpoints — flagged, not faked.)

import { useEffect, useMemo, useState } from "react";
import { LuPanelLeft, LuX, LuSearch, LuPlus, LuPencil, LuArchive, LuTrash2, LuLayoutDashboard, LuFolderPlus, LuFolderInput } from "react-icons/lu";
import { api, type HuntListItem, type Instinct, type Project } from "@/net/api";
import { startNewHunt } from "@/lib/nav";
import { useUiStore } from "@/store/uiStore";

function goTo(path: string) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const STATE_LABEL: Record<string, { text: string; dot: string }> = {
  draft:           { text: "Draft",     dot: "bg-[#52525b]" },
  planning:        { text: "Planning…", dot: "bg-[#5b9bd5]" },
  plan_ready:      { text: "Plan ready",dot: "bg-[#e6a23c]" },
  hunting:         { text: "Hunting…",  dot: "bg-[#3fb27f]" },
  holding:         { text: "On hold",   dot: "bg-[#e6a23c]" },
  standoff:        { text: "Standoff",  dot: "bg-[#c084fc]" },
  finishing:       { text: "Finishing…",dot: "bg-[#3fb27f]" },
  returned:        { text: "Done",      dot: "bg-[#3fb27f]" },
  halted_boundary: { text: "Paused",    dot: "bg-[#e6a23c]" },
  failed:          { text: "Failed",    dot: "bg-[#e03a2f]" },
  stopped_by_user: { text: "Stopped",   dot: "bg-[#52525b]" },
};

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
  const open = useUiStore((s) => s.denOpen);
  const setOpen = useUiStore((s) => s.setDenOpen);
  const [hunts, setHunts] = useState<HuntListItem[]>([]);
  const [instincts, setInstincts] = useState<Instinct[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!open) return;
    Promise.allSettled([api.listHunts(), api.listInstincts(), api.listProjects()]).then(([h, i, p]) => {
      if (h.status === "fulfilled") setHunts(h.value.hunts);
      if (i.status === "fulfilled") setInstincts(i.value.instincts);
      if (p.status === "fulfilled") setProjects(p.value.projects);
      setLoaded(true);
    });
  }, [open]);

  const ql = q.trim().toLowerCase();
  // Scope to the active project (client-side — we already hold every hunt's project_id).
  const scoped = useMemo(
    () => (activeProject ? hunts.filter((h) => h.project_id === activeProject) : hunts),
    [hunts, activeProject],
  );
  const filteredHunts = useMemo(
    () => (ql ? scoped.filter((h) => h.title.toLowerCase().includes(ql)) : scoped),
    [scoped, ql],
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

  function rename(h: HuntListItem) {
    const next = window.prompt("Rename hunt", h.title);
    if (next == null) return;
    const title = next.trim();
    if (!title) return;
    setHunts((hs) => hs.map((x) => (x.hunt_id === h.hunt_id ? { ...x, title } : x)));
    api.patchHunt(h.hunt_id, { title }).catch(() => {});
  }

  function archive(h: HuntListItem) {
    setHunts((hs) => hs.filter((x) => x.hunt_id !== h.hunt_id));
    api.patchHunt(h.hunt_id, { archived: true }).catch(() => {});
  }

  function remove(h: HuntListItem) {
    if (!window.confirm(`Delete "${h.title}"? This can't be undone.`)) return;
    setHunts((hs) => hs.filter((x) => x.hunt_id !== h.hunt_id));
    api.deleteHunt(h.hunt_id).catch(() => {});
  }

  function createProject() {
    const label = window.prompt("New project name")?.trim();
    if (!label) return;
    api.createProject(label).then(({ project_id }) => {
      setProjects((ps) => [
        { project_id, label, instructions: null, hunt_count: 0, created_at: new Date().toISOString() },
        ...ps,
      ]);
      setActiveProject(project_id);
    }).catch(() => {});
  }

  function renameProject(p: Project) {
    const label = window.prompt("Rename project", p.label)?.trim();
    if (!label) return;
    setProjects((ps) => ps.map((x) => (x.project_id === p.project_id ? { ...x, label } : x)));
    api.patchProject(p.project_id, { label }).catch(() => {});
  }

  function deleteProject(p: Project) {
    if (!window.confirm(`Delete project "${p.label}"? Its hunts stay — just unfiled.`)) return;
    setProjects((ps) => ps.filter((x) => x.project_id !== p.project_id));
    setHunts((hs) => hs.map((h) => (h.project_id === p.project_id ? { ...h, project_id: null } : h)));
    if (activeProject === p.project_id) setActiveProject(null);
    api.deleteProject(p.project_id).catch(() => {});
  }

  function assignHunt(h: HuntListItem, projectId: string | null) {
    setHunts((hs) => hs.map((x) => (x.hunt_id === h.hunt_id ? { ...x, project_id: projectId } : x)));
    setProjects((ps) =>
      ps.map((p) => {
        const was = h.project_id === p.project_id;
        const now = projectId === p.project_id;
        if (was === now) return p;
        return { ...p, hunt_count: Math.max(0, p.hunt_count + (now ? 1 : -1)) };
      }),
    );
    api.patchHunt(h.hunt_id, { project_id: projectId }).catch(() => {});
  }

  const activeProj = projects.find((p) => p.project_id === activeProject) ?? null;

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
                  startNewHunt();
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

              {/* Project switcher — filter the Den to one workspace */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 scrollbar-none">
                <ProjChip label="All" active={!activeProject} onClick={() => setActiveProject(null)} />
                {projects.map((p) => (
                  <ProjChip
                    key={p.project_id}
                    label={p.hunt_count ? `${p.label} · ${p.hunt_count}` : p.label}
                    active={activeProject === p.project_id}
                    onClick={() => setActiveProject(p.project_id)}
                  />
                ))}
                <button
                  onClick={createProject}
                  title="New project"
                  className="shrink-0 flex items-center gap-1 rounded-full border border-dashed border-[#3a3a3a] text-[#71717a] hover:text-white hover:border-[#525252] px-2.5 py-1 text-[11px] cursor-pointer bg-transparent"
                >
                  <LuFolderPlus size={12} /> Project
                </button>
              </div>
              {activeProj && (
                <div className="flex items-center gap-2 text-[11px] text-[#71717a] px-0.5">
                  <span>In “{activeProj.label}”</span>
                  <button className="hover:text-white cursor-pointer bg-transparent border-none p-0" onClick={() => renameProject(activeProj)}>
                    Rename
                  </button>
                  <button className="hover:text-[#ff6b5e] cursor-pointer bg-transparent border-none p-0" onClick={() => deleteProject(activeProj)}>
                    Delete
                  </button>
                </div>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6 scrollbar-subtle">
              {huntGroups.length === 0 ? (
                <Empty text={loaded ? (ql ? "No hunts match." : "No hunts yet — send the pack.") : "Loading…"} />
              ) : (
                huntGroups.map((g) => (
                  <Section key={g.label} title={g.label}>
                    {g.items.map((h) => (
                      <HuntRow
                        key={h.hunt_id}
                        hunt={h}
                        projects={projects}
                        onOpen={() => openHunt(h.hunt_id)}
                        onRename={() => rename(h)}
                        onArchive={() => archive(h)}
                        onDelete={() => remove(h)}
                        onAssign={(pid) => assignHunt(h, pid)}
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

function HuntRow({
  hunt,
  projects,
  onOpen,
  onRename,
  onArchive,
  onDelete,
  onAssign,
}: {
  hunt: HuntListItem;
  projects: Project[];
  onOpen: () => void;
  onRename: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onAssign: (projectId: string | null) => void;
}) {
  const [menu, setMenu] = useState(false);
  const act = "p-1 rounded text-[#a1a1aa] hover:text-white hover:bg-white/10 cursor-pointer";
  return (
    <div className="group relative">
      <button
        onClick={onOpen}
        className="text-left bg-[#0F0F0F] border border-[#2a2a2a] rounded-lg pl-3 pr-28 py-2.5 hover:border-[#404040] cursor-pointer w-full"
      >
        <div className="text-[13px] text-white truncate">{hunt.title}</div>
        <div className="text-[11px] text-[#71717a] mt-0.5 flex items-center gap-1.5">
          <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${(STATE_LABEL[hunt.state] ?? STATE_LABEL.draft).dot}`} />
          {(STATE_LABEL[hunt.state] ?? { text: hunt.state }).text}
          <span className="text-[#3a3a3a]">·</span>
          {new Date(hunt.created_at).toLocaleDateString()}
        </div>
      </button>
      <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
        {/* Always-visible canvas button — the main reason to open a past hunt */}
        <button
          className="p-1 rounded text-[#3fb27f] hover:text-white hover:bg-white/10 cursor-pointer"
          title="Open canvas"
          aria-label="Open canvas"
          onClick={onOpen}
        >
          <LuLayoutDashboard size={13} />
        </button>
        {/* Destructive / management actions only on hover */}
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
          <button className={act} title="Move to project" aria-label="Move to project" onClick={() => setMenu((m) => !m)}>
            <LuFolderInput size={13} />
          </button>
          <button className={act} title="Rename" aria-label="Rename" onClick={onRename}>
            <LuPencil size={13} />
          </button>
          <button className={act} title="Archive" aria-label="Archive" onClick={onArchive}>
            <LuArchive size={13} />
          </button>
          <button
            className="p-1 rounded text-[#a1a1aa] hover:text-[#ff6b5e] hover:bg-[#e03a2f]/10 cursor-pointer"
            title="Delete"
            aria-label="Delete"
            onClick={onDelete}
          >
            <LuTrash2 size={13} />
          </button>
        </div>
      </div>
      {menu && (
        <div className="absolute right-1.5 top-full mt-1 z-10 w-44 bg-[#242424] border border-[#2a2a2a] rounded-lg py-1 text-[12px] shadow-lg">
          <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-[#71717a]">Move to project</div>
          <button
            className={`w-full text-left px-3 py-1.5 hover:bg-white/5 ${!hunt.project_id ? "text-white" : "text-[#a1a1aa]"}`}
            onClick={() => { onAssign(null); setMenu(false); }}
          >
            No project
          </button>
          {projects.map((p) => (
            <button
              key={p.project_id}
              className={`w-full text-left px-3 py-1.5 hover:bg-white/5 truncate ${hunt.project_id === p.project_id ? "text-white" : "text-[#a1a1aa]"}`}
              onClick={() => { onAssign(p.project_id); setMenu(false); }}
            >
              {p.label}
            </button>
          ))}
          {projects.length === 0 && <div className="px-3 py-1.5 text-[#52525b]">No projects yet</div>}
        </div>
      )}
    </div>
  );
}

function ProjChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] cursor-pointer border transition-colors ${
        active
          ? "bg-white text-black border-white"
          : "bg-transparent text-[#a1a1aa] border-[#2a2a2a] hover:text-white hover:border-[#3a3a3a]"
      }`}
    >
      {label}
    </button>
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
