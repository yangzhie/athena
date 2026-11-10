import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import { createPlayground, LearningCanvas, presetModules, simulatedPython } from '@athena/playground'
import { ChatPanel } from './ChatPanel'
import { EventLog } from './EventLog'
import { MockAgent, type ChatMessage } from './mockAgent'

/**
 * Demo host. Stands in for the Athena unit page: a chat column (the tutor)
 * next to the Playground Canvas. Only this folder knows about the mock agent
 * and fixtures; the Canvas is used through its public API.
 */
export function DemoApp() {
  const playground = useMemo(() => createPlayground({ modules: presetModules, runtimes: { python: simulatedPython } }), [])
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 0,
      role: 'agent',
      text: "Hi! I'm the tutor for this unit. Ask me whenever something doesn't make sense; when it's easier to try things out, I'll set up an experiment on the Playground on the left.",
    },
  ])
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<'chat' | 'events'>('chat')
  const agent = useMemo(
    () =>
      new MockAgent(
        playground,
        (m) => setMessages((list) => [...list, { ...m, id: list.length }]),
        setBusy,
      ),
    [playground],
  )
  useEffect(() => agent.start(), [agent])
  useEffect(() => {
    // Handy for poking at the canvas from the devtools console.
    if (import.meta.env.DEV) (window as unknown as { playground: unknown }).playground = playground
  }, [playground])

  const state = useSyncExternalStore(playground.subscribe, playground.getState)
  const focusObj = state.selection ? state.objects[state.selection] : null
  const focus = focusObj ? { id: focusObj.id, title: focusObj.title } : null

  const send = (text: string) => {
    setMessages((list) => [...list, { id: list.length, role: 'student', text, about: focus?.title }])
    agent.send(text, focus?.id ?? null)
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-2">
        <span className="font-semibold">Athena</span>
        <span className="text-sm text-muted">Playground Canvas · standalone demo</span>
        <span className="ml-auto rounded bg-warn/15 px-2 py-0.5 text-xs text-warn">mock agent + preset scenes</span>
      </header>
      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1">
          <LearningCanvas playground={playground} />
        </main>
        <aside className="flex w-[380px] shrink-0 flex-col border-l border-line bg-bg">
          <div className="flex gap-1 border-b border-line px-3 pt-2 text-sm">
            {(
              [
                ['chat', 'Chat'],
                ['events', `Events (${playground.getEvents().length})`],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={tab === key ? 'border-b-2 border-accent px-2 pb-1.5 font-medium' : 'px-2 pb-1.5 text-muted hover:text-ink'}
              >
                {label}
              </button>
            ))}
          </div>
          {tab === 'chat' ? (
            <ChatPanel
              messages={messages}
              busy={busy}
              suggestions={agent.suggestions()}
              focus={focus}
              onSend={send}
              onClearFocus={() => playground.select(null)}
            />
          ) : (
            <EventLog playground={playground} />
          )}
        </aside>
      </div>
    </div>
  )
}
