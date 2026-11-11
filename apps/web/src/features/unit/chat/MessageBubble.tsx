import { Link } from 'react-router'
import { Icon } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { ChatMessage, PlaygroundOffer } from '../../../types'
import { playgroundPath } from '../sessions/paths'
import { ActivityCard } from './ActivityCard'
import { SourceList } from './SourceList'
import { transcribeAnswer } from '../../../api/sessions'

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
  layout = 'stack',
  number,
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
  /** lesson: sources sit in a margin column beside the entry (in a wide @container). stack: sources below. */
  layout?: 'stack' | 'lesson'
  /** Question number, for question activities. */
  number?: number
}) {
  // These messages exist only in the student's browser, not in the shared API transcript.
  if (viewer === 'lecturer' && message.via === 'playground') return null

  if (message.role === 'lecturer') {
    return (
      <div className="rounded-md border border-margin/40 bg-surface px-4 py-3 leading-relaxed shadow-[inset_3px_0_0_var(--color-margin)]">
        <p className="mb-1 text-xs font-semibold tracking-[0.14em] text-margin uppercase">{viewer === 'lecturer' ? 'You (lecturer)' : 'Your lecturer'}</p>
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    )
  }

  const localLabel = message.via === 'playground' && (
    <p className="mb-1 text-xs text-muted">🧪 Demo Playground · not saved or shared</p>
  )

  if (message.role === 'learner') {
    // A pen annotation on the page, not a chat bubble.
    const who = viewer === 'lecturer' ? 'Student' : message.answerFor ? 'Your answer' : 'You asked'
    return (
      <div className={cn(layout === 'lesson' && '@2xl:pr-[13rem]')}>
        {localLabel}
        <div className="border-l-2 border-accent/60 pl-4">
          <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">{who}</p>
          <p className={cn('mt-0.5 font-serif text-accent italic whitespace-pre-wrap', compact ? 'text-sm' : 'text-[1.05rem]')}>
            {message.content}
          </p>
        </div>
      </div>
    )
  }

  const sources = (
    <SourceList offeringId={offeringId} sources={message.sources} origin={message.knowledgeOrigin}
      variant={layout === 'lesson' ? 'margin' : 'chips'} />
  )
  // Tutor entries read as the lesson itself; in the lesson layout sources sit in the margin.
  return (
    <div className={cn(
      compact ? 'text-sm leading-relaxed' : 'leading-relaxed',
      layout === 'lesson' && 'grid gap-4 @2xl:grid-cols-[minmax(0,1fr)_11rem] @2xl:gap-8',
    )}>
      <div className="min-w-0">
      {localLabel}
      {message.activity ? (
        <ActivityCard
          key={message.activity.activity_id}
          activity={message.activity}
          open={open && viewer === 'student'}
          busy={busy}
          onAnswer={(a) => onAnswer?.(a)}
          onContinue={() => onContinue?.()}
          number={number}
          transcribe={sessionId && viewer === 'student'
            ? (audio, signal) => transcribeAnswer(offeringId, sessionId, audio, signal) : undefined}
        />
      ) : message.content ? (
        <p className={cn('whitespace-pre-wrap', pending && 'after:ml-0.5 after:animate-pulse after:content-["▍"]')}>
          {message.content}
        </p>
      ) : (
        <p className="flex items-center gap-2 text-sm text-muted italic" aria-label="Athena is thinking">
          Thinking
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
      {layout === 'stack' && sources}
      </div>
      {layout === 'lesson' && <div className="@2xl:pt-1">{sources}</div>}
    </div>
  )
}

/** A demo experiment tied to the same learning session as its chat. */
function PlaygroundCard({ offer, offeringId, sessionId }: { offer: PlaygroundOffer; offeringId: string; sessionId: string }) {
  return (
    <Link
      to={playgroundPath(offeringId, sessionId, offer.sceneId)}
      className="mt-3 flex items-center gap-3 rounded-md border border-dashed border-accent/50 bg-surface p-3 transition-colors hover:border-solid hover:border-accent"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-md bg-accent-soft text-accent" aria-hidden>
        <Icon name="flask" className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{offer.title}</span>
        <span className="block truncate text-xs text-muted">{offer.goal}</span>
      </span>
      <span className="shrink-0 text-sm font-medium text-accent">Open Playground →</span>
    </Link>
  )
}
