import { useState, type FormEvent } from 'react'
import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { AgentActivity } from '../../../types'
import { VoiceAnswerInput } from '../../../components/quiz/VoiceAnswerInput'

interface Props {
  activity: AgentActivity
  /** True for the activity waiting on the learner (the open question, or the latest teaching step). */
  open: boolean
  busy: boolean
  onAnswer: (input: { choiceId?: string; text?: string; shown: string }) => void
  onContinue: () => void
  transcribe?: (audio: Blob, signal: AbortSignal) => Promise<string>
  /** 1-based question number in the session, when known. */
  number?: number
}

/** Feedback outcomes, written like a teacher's pen marks. */
const outcome: Record<string, { label: string; mark: string; className: string }> = {
  correct: { label: 'Correct', mark: '✓', className: 'text-good' },
  partial: { label: 'Partly right', mark: '◐', className: 'text-warn' },
  incorrect: { label: 'Not quite', mark: '✕', className: 'text-bad' },
  uncertain: { label: 'Hard to tell', mark: '?', className: 'text-muted' },
}

const eyebrow = 'text-xs font-semibold tracking-[0.14em] uppercase'

/** Renders one agent activity as part of the lesson, with answer or continue controls when it's open. */
export function ActivityCard({ activity, open, busy, onAnswer, onContinue, transcribe, number }: Props) {
  const [text, setText] = useState('')
  const [voiceBusy, setVoiceBusy] = useState(false)

  if (activity.kind === 'question') {
    const q = activity.question
    const submitText = (e: FormEvent) => {
      e.preventDefault()
      if (text.trim() && !busy && !voiceBusy) onAnswer({ text: text.trim(), shown: text.trim() })
    }
    return (
      <div className={cn(
        'rounded-lg border bg-surface p-5 transition-shadow',
        open ? 'border-accent/50 shadow-[0_0_0_4px_var(--color-accent-soft)]' : 'border-line',
      )}>
        <p className={cn(eyebrow, open ? 'text-accent' : 'text-muted')}>
          {number ? `Question ${number}` : 'Question'}{open && ' · your turn'}
        </p>
        <p className="mt-2 font-serif text-[1.15rem] leading-snug whitespace-pre-wrap">{q.prompt}</p>
        {q.kind === 'multiple_choice' && (
          <div className="mt-4 grid gap-2" role="group" aria-label="Choose an answer">
            {q.choices?.map((c, i) => (
              <button
                key={c.choice_id}
                type="button"
                disabled={!open || busy}
                onClick={() => onAnswer({ choiceId: c.choice_id, shown: c.text })}
                className={cn(
                  'group flex items-start gap-3 rounded-md border border-line bg-bg/40 px-3 py-2.5 text-left transition',
                  open ? 'hover:border-accent hover:bg-accent-soft' : 'opacity-60',
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    'grid size-6 shrink-0 place-items-center rounded-full border border-line font-serif text-sm font-semibold text-muted',
                    open && 'group-hover:border-accent group-hover:bg-accent group-hover:text-surface',
                  )}
                >
                  {String.fromCharCode(65 + i)}
                </span>
                <span className="pt-0.5">{c.text}</span>
              </button>
            ))}
          </div>
        )}
        {q.kind === 'open_ended' && open && (
          <form onSubmit={submitText} className="mt-4 space-y-2">
            <VoiceAnswerInput key={activity.activity_id}
              value={text}
              onChange={setText}
              transcribe={transcribe}
              onBusyChange={setVoiceBusy}
              disabled={busy}
            />
            <Button type="submit" size="sm" disabled={!text.trim() || busy || voiceBusy}>
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
        <p className={cn(eyebrow, 'text-muted')}>Notes</p>
        <p className="whitespace-pre-wrap">{c?.summary ?? activity.text}</p>
        {c?.steps && c.steps.length > 0 && (
          <ol className="space-y-2">
            {c.steps.map((s, i) => (
              <li key={s} className="flex gap-3">
                <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft font-serif text-sm font-semibold text-accent">
                  {i + 1}
                </span>
                <span className="pt-0.5">{s}</span>
              </li>
            ))}
          </ol>
        )}
        {c?.worked_example && (
          // An index card: ruled top line, slightly lifted.
          <div className="rounded-md border border-line bg-surface px-4 pt-2 pb-3 shadow-[0_6px_18px_-14px_color-mix(in_oklab,var(--color-ink)_45%,transparent)]">
            <p className="mb-2 border-b-2 border-margin/40 pb-1 font-serif font-semibold">Worked example</p>
            <p className="whitespace-pre-wrap">{c.worked_example}</p>
          </div>
        )}
        {open && (
          <Button size="sm" onClick={onContinue} disabled={busy}>
            Continue →
          </Button>
        )}
      </div>
    )
  }

  if (activity.kind === 'feedback') {
    const o = activity.content ? outcome[activity.content.outcome] : null
    return (
      <div className="space-y-1.5">
        {o && (
          <p className={cn('flex items-center gap-2 font-serif text-lg font-semibold', o.className)}>
            <span aria-hidden className="text-2xl leading-none">{o.mark}</span>
            {o.label}
          </p>
        )}
        <p className="whitespace-pre-wrap">{activity.content?.message ?? activity.text}</p>
        {activity.content?.next_prompt && <p className="text-muted italic">{activity.content.next_prompt}</p>}
      </div>
    )
  }

  if (activity.kind === 'completion') {
    return (
      <div className="relative overflow-hidden rounded-lg border-2 border-good/50 bg-good/8 p-5">
        <p className="inline-block -rotate-2 rounded-sm border-2 border-good px-2 py-0.5 font-serif text-sm font-bold tracking-[0.12em] text-good uppercase">
          Goal reached
        </p>
        <p className="mt-3 whitespace-pre-wrap">{activity.text}</p>
      </div>
    )
  }

  if (activity.kind === 'hint') {
    return (
      <p className="rounded-md bg-highlight/25 px-3 py-2 whitespace-pre-wrap">
        <span className="font-semibold">Hint: </span>{activity.text}
      </p>
    )
  }

  // rich (diagrams/widgets aren't rendered yet: show their text)
  return <p className="whitespace-pre-wrap">{activity.text}</p>
}
