export type Preset = {
  id: string
  title: string
  desc: string
  prompt: string
}

export const PRESETS: Preset[] = [
  {
    id: 'newsroom',
    title: 'The Newsroom',
    desc: 'Verify claims and write articles',
    prompt: 'Verify this claim: ',
  },
  {
    id: 'meeting',
    title: 'The Meeting Room',
    desc: 'Summarize recordings and decisions',
    prompt: 'Summarise this meeting: ',
  },
  {
    id: 'pipeline',
    title: 'The Pipeline',
    desc: 'Research leads and draft outreach',
    prompt: 'Research and build a brief on: ',
  },
]

interface Props {
  preset: Preset
  onClick: () => void
}

export function PresetCard({ preset, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="text-left rounded-xl px-4 py-3.5 cursor-pointer transition-colors
                 border border-[rgba(255,255,255,0.08)] hover:border-[rgba(255,255,255,0.15)]"
      style={{ backgroundColor: '#111111' }}
    >
      <p className="text-sm font-medium text-white">{preset.title}</p>
      <p className="text-xs mt-1 leading-snug" style={{ color: '#666' }}>{preset.desc}</p>
    </button>
  )
}
