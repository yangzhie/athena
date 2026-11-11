import { useEffect, useRef } from 'react'
import type { LearningSession, Offering } from '../../../types'
import { bumpSession } from '../sessions/sessionStore'
import { Composer } from './Composer'
import { MessageBubble } from './MessageBubble'
import { answer, continueLearning, sendMessage, stopWaiting, useThread } from './chatStore'
import { openActivityId } from './activity'
import { lessonProgress } from './lessonProgress'

function nearBottom() {
  return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160
}

/** One learning session as a lesson: the tutor's steps down the page, sources in the margin, a quiet line to ask on. */
export function UnitChat({ offering, session }: { offering: Offering; session: LearningSession }) {
  const { messages, sending: streaming, error } = useThread(session.id)
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

  const openId = openActivityId(messages)
  const { questionNumber } = lessonProgress(messages)

  const send = (text: string) => {
    bumpSession(session)
    void sendMessage(offering.id, session.id, text)
  }

  return (
    <div className="flex w-full flex-1 flex-col">
      {/* Announce reply state once, rather than every streamed word. */}
      <p className="sr-only" role="status">
        {streaming ? 'Athena is replying' : last?.role === 'tutor' ? 'Athena replied' : ''}
      </p>

      <div className="flex flex-1 flex-col py-6">
        {messages.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center py-16 text-center">
            <h2 className="text-2xl font-semibold">A blank page</h2>
            <p className="mt-2 max-w-md text-muted">
              Ask anything about {session.title}. Answers are based on {offering.unit.code}'s material.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {offering.suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-md border border-line bg-surface px-4 py-2 text-sm transition-colors hover:border-accent hover:text-accent"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            {messages.map((m) => (
              <MessageBubble
                key={m.id}
                message={m}
                layout="lesson"
                number={m.activity?.kind === 'question' ? questionNumber[m.activity.activity_id] : undefined}
                pending={streaming && m.id.startsWith('pending-') && m.role === 'tutor'}
                offeringId={offering.id}
                sessionId={session.id}
                open={!!m.activity && m.activity.activity_id === openId}
                busy={streaming}
                onAnswer={(a) => {
                  if (m.activity?.kind !== 'question') return
                  bumpSession(session)
                  void answer(offering.id, session.id, { questionId: m.activity.question.question_id, ...a })
                }}
                onContinue={() => m.activity && void continueLearning(offering.id, session.id, m.activity.activity_id)}
              />
            ))}
          </div>
        )}
        {error && (
          <p className="mt-4 text-sm text-bad" role="alert">
            This step couldn’t finish: {error.message}
          </p>
        )}
        <div ref={end} className="scroll-mb-40" />
      </div>

      {/* Pinned to the bottom of the viewport; the gradient fades messages scrolling under it. */}
      <div className="sticky bottom-0 bg-linear-to-t from-bg from-70% to-transparent pt-6 pb-4 @2xl:pr-[13rem] md:pb-6">
        <p className="mb-1 px-1 text-xs font-semibold tracking-[0.14em] text-muted uppercase">Stuck? Ask about this step</p>
        <Composer
          placeholder={`Ask anything about ${session.title}…`}
          streaming={streaming}
          onSend={send}
          onStop={() => stopWaiting(session.id)}
        />
        <p className="mt-2 px-1 text-xs text-muted">
          Answers cite {offering.unit.code}'s material in the margin. Anything marked general knowledge isn't from it.
        </p>
      </div>
    </div>
  )
}
