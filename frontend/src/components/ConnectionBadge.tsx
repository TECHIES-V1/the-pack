// Makes the live-stream connection state visible. The canvas renders from the gateway WebSocket; if
// that pipe drops, the canvas would otherwise freeze silently (chat still works over SSE). This badge
// turns that invisible failure into an honest "reconnecting / paused" signal.

type Status = "connecting" | "open" | "closed";

export function ConnectionBadge({ status }: { status: Status }) {
  if (status === "open") return null; // all good — stay out of the way
  const reconnecting = status === "connecting";
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 rounded-full bg-[#1A1A1A] border border-[#2a2a2a] px-3 py-1.5 text-[12px] text-[#d4d4d8] shadow-lg">
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          reconnecting ? "bg-[#e6a23c] animate-pulse" : "bg-[#e03a2f]"
        }`}
      />
      {reconnecting ? "Reconnecting to the live feed…" : "Live updates paused — reconnecting"}
    </div>
  );
}
