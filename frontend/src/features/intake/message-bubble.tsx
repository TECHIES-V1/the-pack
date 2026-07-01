import type { Message } from './use-intake'

interface Props {
  message: Message
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full animate-pulse"
          style={{ backgroundColor: '#555', animationDelay: `${i * 200}ms` }}
        />
      ))}
    </div>
  )
}

export function MessageBubble({ message }: Props) {
  const isAlpha = message.role === 'alpha'

  return (
    <div className="flex flex-col gap-1">
      {isAlpha && (
        <span className="text-[10px] uppercase tracking-widest font-medium" style={{ color: '#555' }}>
          Alpha
        </span>
      )}
      {message.isThinking ? (
        <ThinkingDots />
      ) : (
        <p
          className="text-sm leading-relaxed whitespace-pre-wrap"
          style={{ color: isAlpha ? '#888' : '#f0f0f0' }}
        >
          {message.text}
        </p>
      )}
    </div>
  )
}
