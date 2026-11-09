import { cn } from '../../../lib/cn'
import type { ChatMessage } from '../../../types'

export function MessageBubble({ message, pending }: { message: ChatMessage; pending?: boolean }) {
  if (message.role === 'learner') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-accent-soft px-4 py-2.5 text-[0.9375rem] leading-relaxed whitespace-pre-wrap">
          {message.content}
        </p>
      </div>
    )
  }

  // Tutor replies are full-width text, like Claude or ChatGPT, not a bubble.
  return (
    <div className="text-[0.9375rem] leading-relaxed">
      {message.content ? (
        <p className={cn('whitespace-pre-wrap', pending && 'after:ml-0.5 after:animate-pulse after:content-["▍"]')}>
          {message.content}
        </p>
      ) : (
        <p className="text-muted" aria-label="Athena is thinking">
          <span className="inline-flex gap-1">
            <span className="size-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.2s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-muted [animation-delay:-0.1s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-muted" />
          </span>
        </p>
      )}
    </div>
  )
}
