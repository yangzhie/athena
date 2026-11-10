import { useState, type FormEvent } from 'react'
import type { SrsFeedback, SrsQuestion } from '../../../api/srs'
import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'

interface Props {
  question: SrsQuestion
  /** Set once answered: shows which option was right and locks the form. */
  feedback: SrsFeedback | null
  correct: boolean | null | undefined
  busy: boolean
  onSubmit: (answer: number | string | null) => void
}

const field = 'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent disabled:opacity-70'

/** One SRS question. Grading happens on the server; this only collects the answer. */
export function QuestionForm({ question, feedback, correct, busy, onSubmit }: Props) {
  const [choice, setChoice] = useState<number | null>(null)
  const [text, setText] = useState('')
  const answered = feedback !== null
  const ready = question.kind === 'mcq' ? choice !== null : text.trim() !== ''

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!ready || answered || busy) return
    if (question.kind === 'mcq') onSubmit(choice)
    else if (question.kind === 'numeric') onSubmit(text.trim())
    else onSubmit(text.trim())
  }

  return (
    <form onSubmit={submit}>
      <p className="text-[0.9375rem] leading-relaxed">{question.stem}</p>

      <div className="mt-4">
        {question.kind === 'mcq' && (
          <div className="grid gap-2" role="radiogroup" aria-label="Answer options">
            {question.options?.map((option, i) => {
              const isRight = answered && feedback.correct_option === i
              const isWrongPick = answered && choice === i && correct === false
              return (
                <button
                  key={option}
                  type="button"
                  role="radio"
                  aria-checked={choice === i}
                  disabled={answered}
                  onClick={() => setChoice(i)}
                  className={cn(
                    'flex items-center gap-3 rounded-lg border px-4 py-2.5 text-left text-sm transition',
                    isRight && 'border-good bg-good/10',
                    isWrongPick && 'border-bad bg-bad/10',
                    !answered && choice === i && 'border-accent bg-accent-soft',
                    !answered && choice !== i && 'border-line hover:bg-line/40',
                  )}
                >
                  <span className="font-mono">{option}</span>
                  {isRight && <span className="ml-auto text-xs text-good">✓ correct</span>}
                  {isWrongPick && <span className="ml-auto text-xs text-bad">✕ your answer</span>}
                </button>
              )
            })}
          </div>
        )}
        {question.kind === 'numeric' && (
          <input
            inputMode="decimal"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={answered}
            placeholder="Your answer"
            aria-label="Your answer"
            className={cn(field, 'h-10 max-w-48')}
          />
        )}
        {question.kind === 'short' && (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={answered}
            rows={3}
            placeholder="Answer in a sentence or two"
            aria-label="Your answer"
            className={field}
          />
        )}
      </div>

      {!answered && (
        <Button type="submit" size="sm" disabled={!ready || busy} className="mt-4">
          {busy ? 'Checking…' : 'Check answer'}
        </Button>
      )}
    </form>
  )
}
