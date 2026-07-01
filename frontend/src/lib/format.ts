export function formatUsd(amount: number): string {
  if (amount < 0.01) return `$${(amount * 100).toFixed(2)}¢`
  return `$${amount.toFixed(3)}`
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

export function formatRelative(isoTs: string): string {
  const diff = (Date.now() - new Date(isoTs).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(isoTs).toLocaleDateString()
}

export function formatPct(pct: number): string {
  return `${Math.round(pct * 100)}%`
}
