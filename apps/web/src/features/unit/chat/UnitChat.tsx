import { useEffect, useRef } from 'react'
import type { LearningSession, Offering } from '../../../types'
import { touchSession } from '../sessions/sessionStore'
import { Composer } from './Composer'
import { MessageBubble } from './MessageBubble'
import { sendMessage, stopStreaming, useThread } from './chatStore'

function nearBottom() {
  return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160
}

/** One learning session's chat: messages above, prompt box pinned to the bottom. */
export function UnitChat({ offering, session }: { offering: Offering; session: LearningSession }) {
  const { messages, streaming } = useThread(session.id)
  const end = useRef<HTMLDivElement>(null)
  const lastCount = useRef(messages.length)
  const last = messages.at(-1)

  // Jump to the bottom when a message is added; follow the stream only if
  // the reader hasn't scrolled up to read something earlier.
  useEffect(() => {
    const added = messages.length !== lastCount.current
    lastCount.current = messages.length
    if (added || nearBottom()) end.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, last?.content])

  const send = (text: string) => {
    touchSession(offering.id, session.id)
    void sendMessage(offering, session.id, text)
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col">
      {/* Announce reply state once, rather than every streamed word. */}
      <p className="sr-only" role="status">
        {streaming ? 'Athena is replying' : last?.role === 'tutor' ? 'Athena replied' : ''}
      </p>

      <div className="flex flex-1 flex-col py-6">
        {messages.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center py-16 text-center">
            <h2 className="text-2xl font-semibold tracking-tight">{session.title}</h2>
            <p className="mt-2 max-w-md text-muted">
              Ask anything about it. Answers will be based on {offering.unit.code}'s material.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {offering.suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-line bg-surface px-4 py-2 text-sm transition-colors hover:bg-line/50"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} pending={streaming && m === last} offeringId={offering.id} />
            ))}
          </div>
        )}
        <div ref={end} />
      </div>

      {/* Pinned to the bottom of the viewport; the gradient fades messages scrolling under it. */}
      <div className="sticky bottom-0 bg-linear-to-t from-bg from-70% to-transparent pt-4 pb-4 md:pb-6">
        <Composer
          placeholder={`Message ${offering.unit.code} tutor`}
          streaming={streaming}
          onSend={send}
          onStop={() => stopStreaming(session.id)}
        />
        <p className="mt-2 text-center text-xs text-muted">
          Athena can make mistakes. Check important answers against your unit's material.
        </p>
      </div>
    </div>
  )
}
