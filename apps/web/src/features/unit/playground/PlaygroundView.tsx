import { LearningCanvas } from '@athena/playground'
import { useEffect, useRef, useSyncExternalStore } from 'react'
import { Link, useSearchParams } from 'react-router'
import { playgroundSuggestions } from '../../../api/playground'
import { Composer } from '../chat/Composer'
import { stopStreaming, useThread } from '../chat/chatStore'
import { MessageBubble } from '../chat/MessageBubble'
import { useOffering } from '../useOffering'
import { openScene, sendFromPlayground, sessionFor, usePlaygroundBusy } from './session'

/**
 * The unit's Playground: the canvas, with the unit's tutor thread beside it.
 * `?scene=<id>` opens a scene the tutor offered in the chat.
 */
export default function PlaygroundView() {
  const offering = useOffering()
  const [params] = useSearchParams()
  const sceneId = params.get('scene')
  const { playground } = sessionFor(offering)
  const state = useSyncExternalStore(playground.subscribe, playground.getState)
  const { messages, streaming } = useThread(offering.id)
  const busy = usePlaygroundBusy(offering.id)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (sceneId) void openScene(offering, sceneId)
  }, [offering, sceneId])
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [messages.length])
  useEffect(() => {
    // Handy for poking at the canvas from the devtools console.
    if (import.meta.env.DEV) (window as unknown as { playground: unknown }).playground = playground
  }, [playground])

  const selected = state.selection ? state.objects[state.selection] : null
  const send = (text: string) => void sendFromPlayground(offering, text)
  const hasScene = Boolean(state.scene)

  return (
    <div className="flex flex-1 flex-col gap-4 pb-4 xl:h-[calc(100svh-var(--topbar-h)-3.5rem)] xl:flex-row">
      <section className="relative h-[65svh] min-w-0 overflow-hidden rounded-2xl border border-line xl:h-auto xl:flex-1">
        <LearningCanvas playground={playground} />
      </section>

      <aside className="flex min-h-[24rem] flex-col overflow-hidden rounded-2xl border border-line bg-surface xl:w-[24rem] xl:shrink-0 2xl:w-[28rem]">
        <header className="flex items-center gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted">{offering.unit.code} · Playground</p>
            <h1 className="truncate font-semibold">{state.scene?.title ?? 'Tutor'}</h1>
          </div>
          <Link to={`/units/${offering.id}`} className="shrink-0 text-sm text-accent hover:underline">
            Back to chat
          </Link>
        </header>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} pending={streaming && m === messages.at(-1)} offeringId={offering.id} compact />
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
                    className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs transition-colors hover:bg-line/50"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}
          {busy && <p className="text-xs text-muted">The tutor is thinking…</p>}
          <div ref={end} />
        </div>

        <div className="space-y-2 border-t border-line p-3">
          {hasScene && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {state.scene && (
                <button type="button" onClick={() => send('Can you show me the right way?')} className="rounded-full border border-line px-3 py-1 hover:bg-line/50">
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
            placeholder={selected ? `Ask about “${selected.title}”` : 'Ask the tutor'}
            streaming={streaming}
            onSend={send}
            onStop={() => stopStreaming(offering.id)}
          />
        </div>
      </aside>
    </div>
  )
}
