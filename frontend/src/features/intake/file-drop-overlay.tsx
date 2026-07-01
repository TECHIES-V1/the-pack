export function FileDropOverlay() {
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-5 bg-canvas/85 backdrop-blur-sm">
      <img
        src="/icon-file-drop.svg"
        className="w-16 h-20 opacity-30"
        alt=""
      />
      <p className="text-text-dim text-sm tracking-wide">Drop files here to add to chat</p>
    </div>
  )
}
