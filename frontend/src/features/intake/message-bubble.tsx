import { cn } from '@/lib/utils'
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
          className="w-1.5 h-1.5 rounded-full bg-muted animate-pulse"
          style={{ animationDelay: `${i * 200}ms` }}
        />
      ))}
    </div>
  )
}

export function MessageBubble({ message }: Props) {
  const isAlpha = message.role === 'alpha'

  return (
    <div className={cn('flex flex-col gap-1', isAlpha ? 'items-start' : 'items-start')}>
      {isAlpha && (
        <span className="text-[10px] uppercase tracking-widest text-muted font-medium">
          Alpha
        </span>
      )}
      {message.isThinking ? (
        <ThinkingDots />
      ) : (
        <p
          className={cn(
            'text-sm leading-relaxed whitespace-pre-wrap',
            isAlpha ? 'text-text-dim' : 'text-text',
          )}
        >
          {message.text}
        </p>
      )}
    </div>
  )
}
