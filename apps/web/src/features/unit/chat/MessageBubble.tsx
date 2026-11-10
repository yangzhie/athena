import { cn } from '../../../lib/cn'
import type { ChatMessage } from '../../../types'
import { ActivityCard } from './ActivityCard'
import { SourceList } from './SourceList'

export function MessageBubble({
  message,
  pending,
  offeringId,
  open = false,
  busy = false,
  viewer = 'student',
  onAnswer,
  onContinue,
}: {
  message: ChatMessage
  pending?: boolean
  offeringId: string
  /** This message's activity is the one waiting on the learner. */
  open?: boolean
  busy?: boolean
  onAnswer?: (input: { choiceId?: string; text?: string; shown: string }) => void
  onContinue?: () => void
  /** Who is reading: labels change in a lecturer's view of a shared session. */
  viewer?: 'student' | 'lecturer'
}) {
  if (message.role === 'lecturer') {
    return (
      <div className="rounded-xl border border-accent/40 bg-accent-soft/50 px-4 py-3 text-[0.9375rem] leading-relaxed">
        <p className="mb-1 text-xs font-medium text-accent">{viewer === 'lecturer' ? 'You (lecturer)' : 'Your lecturer'}</p>
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    )
  }

  if (message.role === 'learner') {
    return (
      <div className="flex flex-col items-end">
        {viewer === 'lecturer' && <p className="mb-1 text-xs text-muted">Student</p>}
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-accent-soft px-4 py-2.5 text-[0.9375rem] leading-relaxed whitespace-pre-wrap">
          {message.content}
        </p>
      </div>
    )
  }

  // Tutor replies are full-width text, like Claude or ChatGPT, not a bubble.
  return (
    <div className="text-[0.9375rem] leading-relaxed">
      {message.activity ? (
        <ActivityCard
          activity={message.activity}
          open={open}
          busy={busy}
          onAnswer={(a) => onAnswer?.(a)}
          onContinue={() => onContinue?.()}
        />
      ) : message.content ? (
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
      <SourceList offeringId={offeringId} sources={message.sources} origin={message.knowledgeOrigin} />
    </div>
  )
}
