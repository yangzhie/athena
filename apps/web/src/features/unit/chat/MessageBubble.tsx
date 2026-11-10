import { Link } from 'react-router'
import { cn } from '../../../lib/cn'
import type { ChatMessage, PlaygroundOffer } from '../../../types'
import { playgroundPath } from '../sessions/paths'
import { ActivityCard } from './ActivityCard'
import { SourceList } from './SourceList'

export function MessageBubble({
  message,
  pending,
  offeringId,
  sessionId,
  compact,
  open = false,
  busy = false,
  viewer = 'student',
  onAnswer,
  onContinue,
}: {
  message: ChatMessage
  pending?: boolean
  offeringId: string
  /** Absent in lecturer views: a shared session never links into a student's environment. */
  sessionId?: string
  /** Narrow column beside the Playground. */
  compact?: boolean
  /** This message's activity is the one waiting on the learner. */
  open?: boolean
  busy?: boolean
  onAnswer?: (input: { choiceId?: string; text?: string; shown: string }) => void
  onContinue?: () => void
  /** Who is reading: labels change in a lecturer's view of a shared session. */
  viewer?: 'student' | 'lecturer'
}) {
  // These messages exist only in the student's browser, not in the shared API transcript.
  if (viewer === 'lecturer' && message.via === 'playground') return null

  if (message.role === 'lecturer') {
    return (
      <div className="rounded-xl border border-accent/40 bg-accent-soft/50 px-4 py-3 text-[0.9375rem] leading-relaxed">
        <p className="mb-1 text-xs font-medium text-accent">{viewer === 'lecturer' ? 'You (lecturer)' : 'Your lecturer'}</p>
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    )
  }

  const localLabel = message.via === 'playground' && (
    <p className="mb-1 text-xs text-muted">🧪 Demo Playground · not saved or shared</p>
  )

  if (message.role === 'learner') {
    return (
      <div className="flex flex-col items-end">
        {viewer === 'lecturer' && <p className="mb-1 text-xs text-muted">Student</p>}
        {localLabel}
        <p
          className={cn(
            'max-w-[85%] rounded-2xl rounded-br-sm bg-accent-soft leading-relaxed whitespace-pre-wrap',
            compact ? 'px-3 py-2 text-sm' : 'px-4 py-2.5 text-[0.9375rem]',
          )}
        >
          {message.content}
        </p>
      </div>
    )
  }

  // Tutor replies are full-width text, like Claude or ChatGPT, not a bubble.
  return (
    <div className={compact ? 'text-sm leading-relaxed' : 'text-[0.9375rem] leading-relaxed'}>
      {localLabel}
      {message.activity ? (
        <ActivityCard
          activity={message.activity}
          open={open && viewer === 'student'}
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
      {message.playground && sessionId && viewer === 'student' && (
        <PlaygroundCard offer={message.playground} offeringId={offeringId} sessionId={sessionId} />
      )}
      <SourceList offeringId={offeringId} sources={message.sources} origin={message.knowledgeOrigin} />
    </div>
  )
}

/** A demo experiment tied to the same learning session as its chat. */
function PlaygroundCard({ offer, offeringId, sessionId }: { offer: PlaygroundOffer; offeringId: string; sessionId: string }) {
  return (
    <Link
      to={playgroundPath(offeringId, sessionId, offer.sceneId)}
      className="mt-3 flex items-center gap-3 rounded-xl border border-line bg-surface p-3 transition-colors hover:border-accent"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent-soft text-lg" aria-hidden>
        🧪
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{offer.title}</span>
        <span className="block truncate text-xs text-muted">{offer.goal}</span>
      </span>
      <span className="shrink-0 text-sm font-medium text-accent">Open Playground →</span>
    </Link>
  )
}
