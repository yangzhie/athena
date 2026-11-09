import { useState, type FormEvent } from 'react'
import type { QuizItem } from '../../types'
import { Badge, Button, Card } from '../ui'
import { cn } from '../../lib/cn'

/** "self" = short answer, which the learner marks against the model answer for now. */
export type QuestionResult = 'correct' | 'incorrect' | 'self'

export interface QuestionCardProps {
  item: QuizItem
  title?: string
  /** Show a "Try again" button after checking (Learn) or not (Review). */
  allowRetry?: boolean
  onChecked?: (result: QuestionResult) => void
}

const inputClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent disabled:opacity-70'

/**
 * Renders any QuizItem format with immediate feedback.
 * Grading is local for now; short answers will be LLM-graded against the rubric later.
 */
export function QuestionCard({ item, title = 'Quick check', allowRetry = false, onChecked }: QuestionCardProps) {
  const [selected, setSelected] = useState<number | null>(null)
  const [text, setText] = useState('')
  const [result, setResult] = useState<QuestionResult | null>(null)
  const checked = result !== null

  const canCheck = item.format === 'mcq' ? selected !== null : text.trim() !== ''

  function check(e?: FormEvent) {
    e?.preventDefault()
    if (!canCheck || checked) return
    let r: QuestionResult
    if (item.format === 'mcq') r = selected === item.answer ? 'correct' : 'incorrect'
    else if (item.format === 'numeric') r = Number(text) === Number(item.answer) ? 'correct' : 'incorrect'
    else r = 'self'
    setResult(r)
    onChecked?.(r)
  }

  function reset() {
    setSelected(null)
    setText('')
    setResult(null)
  }

  return (
    <Card title={title} action={<Badge tone="accent">{item.bloom}</Badge>}>
      <form onSubmit={check}>
        <p className="text-sm">{item.stem}</p>

        <div className="mt-4">
          {item.format === 'mcq' && (
            <div className="grid gap-2" role="radiogroup" aria-label="Answer options">
              {item.options?.map((option, i) => {
                const isAnswer = checked && i === item.answer
                const isWrongPick = checked && i === selected && result === 'incorrect'
                return (
                  <button
                    key={option}
                    type="button"
                    role="radio"
                    aria-checked={selected === i}
                    disabled={checked}
                    onClick={() => setSelected(i)}
                    className={cn(
                      'rounded-lg border px-4 py-2.5 text-left text-sm transition',
                      isAnswer && 'border-good bg-good/10',
                      isWrongPick && 'border-bad bg-bad/10',
                      !checked && selected === i && 'border-accent bg-accent-soft',
                      !checked && selected !== i && 'border-line hover:bg-line/40',
                    )}
                  >
                    {option}
                  </button>
                )
              })}
            </div>
          )}

          {item.format === 'numeric' && (
            <input
              type="number"
              inputMode="decimal"
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={checked}
              aria-label="Your answer"
              placeholder="Your answer"
              className={cn(inputClass, 'h-10 max-w-48')}
            />
          )}

          {item.format === 'short' && (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={checked}
              rows={3}
              aria-label="Your answer"
              placeholder="Explain in a sentence or two"
              className={inputClass}
            />
          )}
        </div>

        {checked && item.format !== 'mcq' && (
          <p className="mt-3 rounded-lg bg-line/40 px-3 py-2 text-sm">
            <span className="font-medium">{item.format === 'short' ? 'Model answer: ' : 'Answer: '}</span>
            {item.answer}
          </p>
        )}

        <div className="mt-4 flex items-center gap-3">
          {checked ? (
            <>
              <p
                className={cn(
                  'text-sm font-medium',
                  result === 'correct' && 'text-good',
                  result === 'incorrect' && 'text-bad',
                  result === 'self' && 'text-muted',
                )}
              >
                {result === 'correct' && 'Correct!'}
                {result === 'incorrect' && 'Not quite. The correct answer is shown.'}
                {result === 'self' && 'Compare your answer with the model answer.'}
              </p>
              {allowRetry && (
                <Button variant="ghost" size="sm" onClick={reset}>
                  Try again
                </Button>
              )}
            </>
          ) : (
            <Button type="submit" size="sm" disabled={!canCheck}>
              Check answer
            </Button>
          )}
        </div>
      </form>
    </Card>
  )
}
