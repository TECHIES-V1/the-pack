export function PlanPage() {
  const huntId = window.location.pathname.split("/plan/")[1] ?? "unknown";

  return (
    <div className="fixed inset-0 bg-door-bg text-white font-sans flex flex-col items-center justify-center gap-3">
      <p className="text-door-dim text-sm tracking-wide uppercase">Plan page</p>
      <h1 className="text-[32px] font-normal tracking-tight m-0">Coming soon</h1>
      <p className="text-door-dim text-xs font-mono">{huntId}</p>
      <button
        onClick={() => {
          window.history.pushState({}, "", "/door");
          window.dispatchEvent(new PopStateEvent("popstate"));
        }}
        className="mt-4 text-[13px] text-door-dim hover:text-white transition-colors border border-door-border rounded-lg px-4 py-2 bg-transparent cursor-pointer font-sans"
      >
        ← Back to Door
      </button>
    </div>
  );
}
