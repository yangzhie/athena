import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, QuickReply } from './mockAgent'

const ORIGIN = {
  prepared: 'Prepared with the scene · no model call',
  model: 'Handed to the model (question / unmatched action)',
} as const

/** Inline `code` only; the mock agent writes nothing fancier. */
function renderText(text: string) {
  return text.split(/(`[^`]+`)/g).map((p, i) =>
    p.startsWith('`') ? (
      <code key={i} className="rounded bg-bg px-1 font-mono text-[0.9em]">
        {p.slice(1, -1)}
      </code>
    ) : (
      p
    ),
  )
}

type Props = {
  messages: ChatMessage[]
  busy: boolean
  suggestions: QuickReply[]
  focus: { id: string; title: string } | null
  onSend: (text: string) => void
  onClearFocus: () => void
}

export function ChatPanel({ messages, busy, suggestions, focus, onSend, onClearFocus }: Props) {
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, busy])

  const send = (text: string) => {
    if (!text.trim() || busy) return
    onSend(text.trim())
    setDraft('')
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((m) =>
          m.role === 'student' ? (
            <div key={m.id} className="ml-8 rounded-2xl rounded-br-sm bg-accent px-3 py-2 text-sm text-white">
              {m.about && <p className="mb-0.5 text-[11px] opacity-80">About: {m.about}</p>}
              {m.text}
            </div>
          ) : (
            <div key={m.id} className="mr-4 space-y-1.5">
              <div className="rounded-2xl rounded-bl-sm border border-line bg-surface px-3 py-2 text-sm leading-relaxed">
                {m.origin && <p className="mb-1 text-[11px] text-muted">{ORIGIN[m.origin]}</p>}
                {renderText(m.text)}
              </div>
              {m.tools && m.tools.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {m.tools.map((t, i) => (
                    <span key={i} className="rounded border border-line bg-bg px-1.5 py-0.5 font-mono text-[10px] text-muted">
                      🔧 {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ),
        )}
        {busy && <p className="text-xs text-muted">The tutor is thinking…</p>}
        <div ref={endRef} />
      </div>

      <div className="space-y-2 border-t border-line p-3">
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s.label}
              type="button"
              disabled={busy}
              onClick={() => send(s.text)}
              className="rounded-full border border-accent/40 px-2.5 py-1 text-xs text-accent hover:bg-accent-soft disabled:opacity-50"
            >
              {s.label}
            </button>
          ))}
        </div>
        {focus && (
          <div className="flex items-center gap-1 text-xs text-muted">
            <span className="rounded bg-accent-soft px-1.5 py-0.5 text-accent">About: {focus.title}</span>
            <button type="button" className="hover:text-ink" onClick={onClearFocus} title="Clear selection">
              ×
            </button>
          </div>
        )}
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            send(draft)
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={focus ? `Ask about “${focus.title}”…` : 'Ask a question…'}
            className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <button type="submit" disabled={busy || !draft.trim()} className="rounded-lg bg-accent px-3 text-sm text-white disabled:opacity-50">
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
