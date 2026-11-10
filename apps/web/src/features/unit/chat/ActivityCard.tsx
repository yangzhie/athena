import { useState, type FormEvent } from 'react'
import { Badge, Button, type Tone } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { AgentActivity } from '../../../types'

interface Props {
  activity: AgentActivity
  /** True for the activity waiting on the learner (the open question, or the latest teaching step). */
  open: boolean
  busy: boolean
  onAnswer: (input: { choiceId?: string; text?: string; shown: string }) => void
  onContinue: () => void
}

const outcome: Record<string, { label: string; icon: string; tone: Tone }> = {
  correct: { label: 'Correct', icon: '✓', tone: 'good' },
  partial: { label: 'Partly right', icon: '◐', tone: 'warn' },
  incorrect: { label: 'Not quite', icon: '✕', tone: 'bad' },
  uncertain: { label: 'Hard to tell', icon: '?', tone: 'neutral' },
}

/** Renders one agent activity inside the chat, with answer or continue controls when it's open. */
export function ActivityCard({ activity, open, busy, onAnswer, onContinue }: Props) {
  const [text, setText] = useState('')

  if (activity.kind === 'question') {
    const q = activity.question
    const submitText = (e: FormEvent) => {
      e.preventDefault()
      if (text.trim()) onAnswer({ text: text.trim(), shown: text.trim() })
    }
    return (
      <div className="rounded-xl border border-line bg-surface p-4">
        <p className="mb-1 text-xs font-medium tracking-wide text-muted uppercase">Question</p>
        <p className="whitespace-pre-wrap">{q.prompt}</p>
        {q.kind === 'multiple_choice' && (
          <div className="mt-3 grid gap-2" role="group" aria-label="Choose an answer">
            {q.choices?.map((c) => (
              <button
                key={c.choice_id}
                type="button"
                disabled={!open || busy}
                onClick={() => onAnswer({ choiceId: c.choice_id, shown: c.text })}
                className={cn(
                  'rounded-lg border border-line px-4 py-2.5 text-left text-sm transition',
                  open ? 'hover:border-accent hover:bg-accent-soft' : 'opacity-70',
                )}
              >
                {c.text}
              </button>
            ))}
          </div>
        )}
        {q.kind === 'open_ended' && open && (
          <form onSubmit={submitText} className="mt-3 space-y-2">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={3}
              placeholder="Your answer"
              aria-label="Your answer"
              disabled={busy}
              className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
            />
            <Button type="submit" size="sm" disabled={!text.trim() || busy}>
              Answer
            </Button>
          </form>
        )}
      </div>
    )
  }

  if (activity.kind === 'explanation') {
    const c = activity.content
    return (
      <div className="space-y-3">
        <p className="whitespace-pre-wrap">{c?.summary ?? activity.text}</p>
        {c?.steps && c.steps.length > 0 && (
          <ol className="list-decimal space-y-1 pl-5">
            {c.steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
        )}
        {c?.worked_example && (
          <div className="rounded-lg bg-line/40 px-4 py-3 text-sm">
            <p className="mb-1 font-medium">Worked example</p>
            <p className="whitespace-pre-wrap">{c.worked_example}</p>
          </div>
        )}
        {open && (
          <Button size="sm" onClick={onContinue} disabled={busy}>
            Continue
          </Button>
        )}
      </div>
    )
  }

  if (activity.kind === 'feedback') {
    const o = activity.content ? outcome[activity.content.outcome] : null
    return (
      <div className="space-y-2">
        {o && (
          <Badge tone={o.tone}>
            <span aria-hidden>{o.icon}</span>&nbsp;{o.label}
          </Badge>
        )}
        <p className="whitespace-pre-wrap">{activity.content?.message ?? activity.text}</p>
        {activity.content?.next_prompt && <p className="text-muted">{activity.content.next_prompt}</p>}
      </div>
    )
  }

  if (activity.kind === 'completion') {
    return (
      <div className="space-y-2 rounded-xl border border-good/40 bg-good/10 p-4">
        <Badge tone="good">✓ Session goal reached</Badge>
        <p className="whitespace-pre-wrap">{activity.text}</p>
      </div>
    )
  }

  // hint, rich (diagrams/widgets aren't rendered yet: show their text)
  return <p className="whitespace-pre-wrap">{activity.text}</p>
}
