import { LearningCanvas } from '@athena/playground'
import { useEffect, useRef, useSyncExternalStore } from 'react'
import { Link, useSearchParams } from 'react-router'
import { cancelExecution, playgroundSuggestions } from '../../../api/playground'
import type { LearningSession } from '../../../types'
import { openActivityId } from '../chat/activity'
import { Composer } from '../chat/Composer'
import { answer, continueLearning, stopWaiting, useThread } from '../chat/chatStore'
import { MessageBubble } from '../chat/MessageBubble'
import { SessionGate } from '../sessions/SessionGate'
import { sessionPath } from '../sessions/paths'
import { bumpSession } from '../sessions/sessionStore'
import { useOffering } from '../useOffering'
import { openScene, sendFromPlayground, sessionFor, usePlaygroundBusy, usePlaygroundDetails, restoreCanvas, retryCanvas, replacementDecision } from './session'

/** The canvas belongs to the learning session in the route, never to a whole offering. */
export default function PlaygroundView() {
  return <SessionGate>{(session) => <SessionPlayground key={session.id} session={session} />}</SessionGate>
}

/** `?scene=<id>` opens the demo offered in this session's chat. */
function SessionPlayground({ session }: { session: LearningSession }) {
  const offering = useOffering()
  const [params] = useSearchParams()
  const sceneId = params.get('scene')
  const { playground } = sessionFor(offering, session.id)
  const state = useSyncExternalStore(playground.subscribe, playground.getState)
  const { messages, sending: streaming, error } = useThread(session.id)
  const busy = usePlaygroundBusy(session.id)
  const detail = usePlaygroundDetails(session.id)
  const thread = useRef<HTMLDivElement>(null)

  useEffect(() => {
    void restoreCanvas(offering, session.id)
    const timer = setInterval(() => { if (!document.hidden) void restoreCanvas(offering, session.id) }, 2000)
    return () => clearInterval(timer)
  }, [offering, session.id])
  useEffect(() => {
    if (sceneId) void openScene(offering, session.id, sceneId)
  }, [offering, session.id, sceneId])
  useEffect(() => {
    // Chat uses document scrolling; don't carry its scroll position into the canvas view.
    window.scrollTo(0, 0)
  }, [session.id])
  useEffect(() => {
    // Scroll only the thread, never the document containing the canvas.
    const el = thread.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages.length])
  useEffect(() => {
    // Handy for poking at the canvas from the devtools console.
    if (!import.meta.env.DEV) return
    const debugWindow = window as unknown as { playground?: unknown }
    debugWindow.playground = playground
    return () => { if (debugWindow.playground === playground) delete debugWindow.playground }
  }, [playground])

  const selected = state.selection ? state.objects[state.selection] : null
  const send = (text: string) => void sendFromPlayground(offering, session.id, text)
  const hasScene = Boolean(state.scene)
  const openId = openActivityId(messages)

  return (
    <div className="flex flex-1 flex-col gap-4 pb-4 xl:h-[calc(100svh-var(--topbar-h)-3.5rem)] xl:flex-none xl:flex-row">
      <section className="relative h-[65svh] min-h-0 min-w-0 shrink-0 overflow-hidden rounded-2xl border border-line xl:h-auto xl:flex-1">
        <LearningCanvas playground={playground} />
        {detail.replacements.map((proposal) => <div key={proposal.id} className="absolute top-3 left-3 right-3 rounded-xl border border-line bg-surface p-3 text-sm">
          <p>The tutor proposes replacing your work with “{proposal.scene.title}”: {proposal.scene.goal}</p>
          <button className="m-2 text-accent" onClick={() => void replacementDecision(offering, session.id, proposal.id, 'accept')}>Replace my work</button>
          <button className="m-2" onClick={() => void replacementDecision(offering, session.id, proposal.id, 'reject')}>Keep my work</button>
        </div>)}
      </section>

      <aside className="flex h-[24rem] min-h-0 shrink-0 flex-col overflow-hidden rounded-2xl border border-line bg-surface xl:h-auto xl:w-[24rem] 2xl:w-[28rem]">
        <header className="flex items-center gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted">{offering.unit.code} · Playground</p>
            <h1 className="truncate font-semibold">{state.scene?.title ?? session.title}</h1>
          </div>
          <Link to={sessionPath(offering.id, session.id)} className="shrink-0 text-sm text-accent hover:underline">
            Back to chat
          </Link>
        </header>

        <div ref={thread} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
          {messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
              pending={streaming && m.id.startsWith('pending-') && m.role === 'tutor'}
              offeringId={offering.id}
              sessionId={session.id}
              compact
              open={!!m.activity && m.activity.activity_id === openId}
              busy={streaming || busy}
              onAnswer={(a) => {
                if (m.activity?.kind !== 'question') return
                bumpSession(session)
                void answer(offering.id, session.id, { questionId: m.activity.question.question_id, ...a })
              }}
              onContinue={() => m.activity && void continueLearning(offering.id, session.id, m.activity.activity_id)}
            />
          ))}
          {!hasScene && (
            <div className="space-y-2 pt-2">
              <p className="text-sm text-muted">Ask something that's easier to try than to read, and the tutor will set up an experiment here.</p>
              <div className="flex flex-wrap gap-2">
                {playgroundSuggestions().map((s) => (
                  <button
                    key={s.label}
                    type="button"
                    onClick={() => send(s.text)}
                    disabled={streaming || busy}
                    className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs transition-colors hover:bg-line/50"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}
          {busy && <p className="text-xs text-muted">Athena is thinking…</p>}
          {detail.error && <div role="alert" className="text-sm text-bad">{detail.error} <button className="underline" onClick={() => void retryCanvas(offering, session.id)}>Retry / refresh</button></div>}
          {detail.executions.slice(-3).map((job) => <div key={job.id} className="rounded border border-line p-2 text-xs">
            <p>Python: {job.state} {job.result && '· verified execution'}</p>
            {job.result?.stdout && <pre className="max-h-32 overflow-auto whitespace-pre-wrap">{job.result.stdout}</pre>}
            {(job.error || job.result?.error) && <p className="text-bad">{job.error || job.result?.error?.message}</p>}
            {['queued', 'running'].includes(job.state) && <button className="text-accent" onClick={() => void cancelExecution(offering, session.id, job.id).then(() => restoreCanvas(offering, session.id))}>Cancel run</button>}
          </div>)}
          {error && <p className="text-sm text-bad" role="alert">{error.message}</p>}
        </div>

        <div className="space-y-2 border-t border-line p-3">
          <p className="text-xs text-muted">Your canvas and discussion are saved privately with this session. Sharing includes this discussion. Canvas checks alone do not establish mastery.</p>
          {hasScene && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {state.scene && (
                <button type="button" disabled={streaming || busy} onClick={() => send('Can you show me the right way?')} className="rounded-full border border-line px-3 py-1 hover:bg-line/50">
                  Show me how
                </button>
              )}
              {selected && (
                <span className="rounded-full bg-accent-soft px-2.5 py-1 text-accent">
                  About: {selected.title}
                  <button type="button" onClick={() => playground.select(null)} className="ml-1.5 text-muted hover:text-ink" aria-label="Clear">
                    ×
                  </button>
                </span>
              )}
            </div>
          )}
          <Composer
            placeholder={selected ? `Ask about “${selected.title}”` : 'Ask the Playground tutor'}
            streaming={streaming}
            disabled={busy}
            onSend={send}
            onStop={() => stopWaiting(session.id)}
          />
        </div>
      </aside>
    </div>
  )
}
