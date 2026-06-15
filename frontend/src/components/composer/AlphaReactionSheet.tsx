interface AlphaReactionSheetProps {
  file: File;
  onDismiss: () => void;
  onAction: (action: string) => void;
}

function getReaction(file: File): { message: string; actions: string[] } {
  const name = file.name.toLowerCase();
  const type = file.type;
  const sizeMB = (file.size / (1024 * 1024)).toFixed(0);

  if (type.startsWith("audio/")) {
    const mins = Math.round((file.size / 1024 / 1024) * 4);
    return {
      message: `A recording, ~${mins} minutes. What do you want from it?`,
      actions: ["Decisions & action items", "Summary to send", "Both"],
    };
  }

  if (type === "application/pdf" || name.endsWith(".pdf")) {
    const pages = Math.max(1, Math.round(file.size / 3000));
    return {
      message: `A document, ~${pages} pages. What should Alpha do with it?`,
      actions: ["Summarise it", "Flag risks", "Both"],
    };
  }

  if (type.startsWith("video/")) {
    return {
      message: `A video file, ${sizeMB}MB. Want a transcript, a summary, or key moments?`,
      actions: ["Transcript", "Summary", "Key moments"],
    };
  }

  if (type.startsWith("image/")) {
    return {
      message: `An image. Want me to describe it, extract text, or analyse it?`,
      actions: ["Describe it", "Extract text", "Analyse"],
    };
  }

  if (
    name.endsWith(".csv") ||
    name.endsWith(".xlsx") ||
    name.endsWith(".xls")
  ) {
    return {
      message: `A spreadsheet. Want a summary, insights, or specific data pulled out?`,
      actions: ["Summarise", "Find insights", "Pull specific data"],
    };
  }

  return {
    message: `Got the file — ${file.name}. What should Alpha do with it?`,
    actions: ["Summarise it", "Extract key info", "Ask me questions"],
  };
}

export function AlphaReactionSheet({ file, onDismiss, onAction }: AlphaReactionSheetProps) {
  const { message, actions } = getReaction(file);

  return (
    <div className="w-[min(880px,90vw)] bg-door-surface border border-door-border rounded-2xl px-5 py-3.5 flex flex-col gap-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          {/* Alpha indicator dot */}
          <span className="w-2 h-2 rounded-full bg-white inline-block shrink-0 mt-0.5" />
          <p className="text-white text-[15px] leading-snug m-0">{message}</p>
        </div>
        <button
          onClick={onDismiss}
          className="bg-transparent border-none text-door-dim cursor-pointer p-0 flex items-center shrink-0 hover:text-white transition-colors"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        {actions.map((action) => (
          <button
            key={action}
            onClick={() => onAction(action)}
            className="bg-transparent border border-door-border rounded-lg px-4 py-2 text-[13px] text-white cursor-pointer hover:border-[#555] hover:bg-white/5 transition-colors font-sans"
          >
            {action}
          </button>
        ))}
      </div>
    </div>
  );
}
