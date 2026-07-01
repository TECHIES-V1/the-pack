import type { AttachedFile } from './use-intake'

interface Props {
  file: AttachedFile
  onRemove: (localId: string) => void
}

export function FileChip({ file, onRemove }: Props) {
  return (
    <div className="flex items-center gap-1.5 bg-surface border border-border rounded-md px-2.5 py-1.5">
      <img src="/icon-file.svg" className="w-3 h-3 opacity-50" alt="" />
      <span className="text-xs text-text-dim truncate max-w-[120px]">{file.name}</span>
      <button
        onClick={() => onRemove(file.localId)}
        className="text-muted hover:text-danger transition-colors ml-0.5 leading-none"
        aria-label={`Remove ${file.name}`}
      >
        ✕
      </button>
    </div>
  )
}
