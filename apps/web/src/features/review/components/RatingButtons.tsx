import { Button } from '../../../components/ui'
import type { QuestionResult } from '../../../components/quiz'

/** FSRS ratings. The scheduler uses these to pick the next interval. */
export type Rating = 'again' | 'hard' | 'good' | 'easy'

const ratings: { value: Rating; label: string; hint: string }[] = [
  { value: 'again', label: 'Again', hint: '< 10 min' },
  { value: 'hard', label: 'Hard', hint: '1 day' },
  { value: 'good', label: 'Good', hint: '3 days' },
  { value: 'easy', label: 'Easy', hint: '7 days' },
]

/** A wrong answer can only be rated "Again", as in FSRS. Intervals are placeholders. */
export function RatingButtons({ result, onRate }: { result: QuestionResult; onRate: (r: Rating) => void }) {
  const options = result === 'incorrect' ? ratings.slice(0, 1) : ratings
  return (
    <div>
      <p className="mb-2 text-sm text-muted">How well did you know it?</p>
      <div className="flex flex-wrap gap-2">
        {options.map((r) => (
          <Button key={r.value} variant={r.value === 'good' ? 'primary' : 'secondary'} onClick={() => onRate(r.value)}>
            {r.label}
            <span className="text-xs opacity-70">{r.hint}</span>
          </Button>
        ))}
      </div>
    </div>
  )
}
