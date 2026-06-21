// A clear status bar for terminal hunt states the chat rail doesn't already handle — so a stopped
// or failed hunt no longer looks identical to a running one. (halted_boundary is handled by the
// rail's "Boundary reached" panel, so it's deliberately NOT duplicated here.)

function goHome() {
  window.history.pushState({}, "", "/");
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const SHOWN = new Set(["failed", "stopped_by_user"]);

export function HuntStatusBanner({ state }: { state: string }) {
  if (!SHOWN.has(state)) return null;

  const failed = state === "failed";
  const tone = failed ? "#eb3424" : "#a1a1aa";
  const text = failed ? "The pack couldn't finish this one." : "You stopped the hunt.";
  const action = failed ? "Try a new hunt" : "Start a new hunt";

  return (
    <div
      className="shrink-0 flex items-center justify-between gap-4 mx-2 mt-2 px-4 py-2.5 rounded-[10px] border"
      style={{ borderColor: `${tone}55`, background: `${tone}14` }}
    >
      <span className="text-[13px]" style={{ color: tone }}>
        {text}
      </span>
      <button
        onClick={goHome}
        className="shrink-0 rounded-lg px-3.5 py-1.5 text-[12.5px] font-medium text-black bg-white hover:bg-white/90 cursor-pointer border-none"
      >
        {action}
      </button>
    </div>
  );
}
