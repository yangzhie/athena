import { useEffect, useRef } from 'react'
import type { Rating, SrsAttemptResult } from '../../../api/srs'
import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'

const ratingLabel: Record<Rating, { label: string; hint: string }> = {
  again: { label: 'Again', hint: 'I didn’t know it' },
  hard: { label: 'Hard', hint: 'Got it, with effort' },
  good: { label: 'Good', hint: 'Got it' },
  easy: { label: 'Easy', hint: 'Too easy' },
}

interface Props {
  result: SrsAttemptResult
  busy: boolean
  onRate: (rating: Rating) => void
  onNext: () => void
}

export function FeedbackPanel({ result, busy, onRate, onNext }: Props) {
  const heading = useRef<HTMLHeadingElement>(null)
  const { correct, feedback } = result

  // Move focus to the result so keyboard and screen-reader users land on it.
  useEffect(() => heading.current?.focus(), [])

  return (
    <div className="mt-5 space-y-4 border-t border-line pt-5">
      <h3
        ref={heading}
        tabIndex={-1}
        className={cn('font-semibold outline-none', correct === true && 'text-good', correct === false && 'text-bad')}
      >
        {correct === true && '✓ Correct'}
        {correct === false && '✕ Not quite'}
        {correct === null && 'Compare with the model answer'}
      </h3>

      {feedback.correct_value !== undefined && (
        <p className="text-sm">
          Answer: <span className="font-mono font-medium">{feedback.correct_value}</span>
        </p>
      )}
      {feedback.model_answer && (
        <div className="rounded-lg bg-line/40 px-4 py-3 text-sm">
          <p className="font-medium">Model answer</p>
          <p className="mt-1">{feedback.model_answer}</p>
          {feedback.rubric && feedback.rubric.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-muted">
              {feedback.rubric.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      <p className="text-sm text-muted">{feedback.explanation}</p>

      {result.needs_rating ? (
        <div>
          <p className="mb-2 text-sm text-muted">
            {correct === null ? 'How close was your answer?' : 'How well did you know it?'}
          </p>
          <div className="flex flex-wrap gap-2">
            {(result.rating_options ?? []).map((r) => (
              <Button
                key={r}
                variant={r === 'good' ? 'primary' : 'secondary'}
                size="sm"
                disabled={busy}
                onClick={() => onRate(r)}
                title={ratingLabel[r].hint}
              >
                {ratingLabel[r].label}
              </Button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm">This idea will come back soon, worded differently.</p>
          <Button size="sm" onClick={onNext} disabled={busy}>
            Next question
          </Button>
        </div>
      )}
    </div>
  )
}
