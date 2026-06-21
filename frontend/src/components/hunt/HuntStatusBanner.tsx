// A clear status bar for terminal hunt states — so a stopped / out-of-budget / failed hunt no
// longer looks identical to a running one, and each comes with a real recovery action.

import { api } from "@/net/api";

function goHome() {
  window.history.pushState({}, "", "/");
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const TERMINAL = new Set(["failed", "halted_boundary", "stopped_by_user"]);

export function HuntStatusBanner({
  state,
  huntId,
  boundaryUsd,
}: {
  state: string;
  huntId: string;
  boundaryUsd: number;
}) {
  if (!TERMINAL.has(state)) return null;

  const resume = () => {
    const next = boundaryUsd > 0 ? Math.max(boundaryUsd * 2, boundaryUsd + 1) : 2;
    api.resume(huntId, next).catch(() => {});
  };

  let tone = "#e6a23c";
  let text = "";
  let actions: { label: string; onClick: () => void; primary?: boolean }[] = [];

  if (state === "failed") {
    tone = "#eb3424";
    text = "The pack couldn't finish this one.";
    actions = [{ label: "Try a new hunt", onClick: goHome, primary: true }];
  } else if (state === "halted_boundary") {
    tone = "#e6a23c";
    text = `Hit the spend boundary ($${boundaryUsd.toFixed(2)}) — the pack paused.`;
    actions = [
      { label: "Raise boundary & resume", onClick: resume, primary: true },
      { label: "New hunt", onClick: goHome },
    ];
  } else if (state === "stopped_by_user") {
    tone = "#a1a1aa";
    text = "You stopped the hunt.";
    actions = [{ label: "New hunt", onClick: goHome, primary: true }];
  }

  return (
    <div
      className="shrink-0 flex items-center justify-between gap-4 mx-2 mt-2 px-4 py-2.5 rounded-[10px] border"
      style={{ borderColor: `${tone}55`, background: `${tone}14` }}
    >
      <span className="text-[13px]" style={{ color: tone }}>
        {text}
      </span>
      <div className="flex items-center gap-2 shrink-0">
        {actions.map((a) => (
          <button
            key={a.label}
            onClick={a.onClick}
            className={
              a.primary
                ? "rounded-lg px-3.5 py-1.5 text-[12.5px] font-medium text-black bg-white hover:bg-white/90 cursor-pointer border-none"
                : "rounded-lg px-3.5 py-1.5 text-[12.5px] text-[#a1a1aa] bg-transparent border border-[#2a2a2a] hover:text-white cursor-pointer"
            }
          >
            {a.label}
          </button>
        ))}
      </div>
    </div>
  );
}
