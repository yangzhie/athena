import { useState } from 'react'
import type { QuizItem } from '../../../types'
import { Badge, Button, Card } from '../../../components/ui'
import { cn } from '../../../lib/cn'

/** A multiple-choice question with immediate feedback. Grading is local for now. */
export function QuestionCard({ item }: { item: QuizItem }) {
  const [selected, setSelected] = useState<number | null>(null)
  const [checked, setChecked] = useState(false)
  const correct = checked && selected === item.answer

  return (
    <Card title="Quick check" action={<Badge tone="accent">{item.bloom}</Badge>}>
      <p className="text-sm">{item.stem}</p>

      <div className="mt-4 grid gap-2" role="radiogroup" aria-label="Answer options">
        {item.options?.map((option, i) => {
          const isAnswer = checked && i === item.answer
          const isWrongPick = checked && i === selected && !correct
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

      <div className="mt-4 flex items-center gap-3">
        {checked ? (
          <>
            <p className={cn('text-sm font-medium', correct ? 'text-good' : 'text-bad')}>
              {correct ? 'Correct!' : 'Not quite. The highlighted answer is correct.'}
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSelected(null)
                setChecked(false)
              }}
            >
              Try again
            </Button>
          </>
        ) : (
          <Button size="sm" disabled={selected === null} onClick={() => setChecked(true)}>
            Check answer
          </Button>
        )}
      </div>
    </Card>
  )
}
