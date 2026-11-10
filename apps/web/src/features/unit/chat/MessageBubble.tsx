import { Link } from 'react-router'
import { cn } from '../../../lib/cn'
import type { ChatMessage, PlaygroundOffer } from '../../../types'
import { SourceList } from './SourceList'

export function MessageBubble({
  message,
  pending,
  offeringId,
  compact,
}: {
  message: ChatMessage
  pending?: boolean
  offeringId: string
  /** Narrow column beside the Playground. */
  compact?: boolean
}) {
  if (message.role === 'learner') {
    return (
      <div className="flex justify-end">
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
      {message.via === 'playground' && !compact && <p className="mb-1 text-xs text-muted">🧪 On the Playground</p>}
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
      {message.playground && <PlaygroundCard offer={message.playground} offeringId={offeringId} />}
      <SourceList offeringId={offeringId} sources={message.sources} origin={message.knowledgeOrigin} />
    </div>
  )
}

/** The tutor set up an experiment for this question. */
function PlaygroundCard({ offer, offeringId }: { offer: PlaygroundOffer; offeringId: string }) {
  return (
    <Link
      to={`/units/${offeringId}/playground?scene=${encodeURIComponent(offer.sceneId)}`}
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
