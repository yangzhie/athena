import { useState } from 'react'
import { Link, useLoaderData } from 'react-router'
import { Badge, Card, buttonStyles } from '../../components/ui'
import { QuestionCard, type QuestionResult } from '../../components/quiz'
import { RatingButtons, type Rating } from './components/RatingButtons'
import type { reviewLoader } from './loader'

export default function ReviewPage() {
  const { due, topicTitles } = useLoaderData<typeof reviewLoader>()
  const [index, setIndex] = useState(0)
  const [result, setResult] = useState<QuestionResult | null>(null)
  // Collected locally; will be sent to the SRS engine later.
  const [ratings, setRatings] = useState<Rating[]>([])

  if (due.length === 0 || index >= due.length) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <h1 className="text-xl font-semibold">All caught up</h1>
          <p className="mt-1 text-sm text-muted">
            {ratings.length > 0
              ? `You reviewed ${ratings.length} item${ratings.length === 1 ? '' : 's'}. Next reviews are scheduled automatically.`
              : 'Nothing is due right now. Keep learning and Athena will schedule reviews for you.'}
          </p>
          <Link to="/learn" className={buttonStyles('secondary', 'sm', 'mt-4')}>
            Keep learning
          </Link>
        </Card>
      </div>
    )
  }

  const item = due[index]

  function rate(r: Rating) {
    setRatings((prev) => [...prev, r])
    setResult(null)
    setIndex((i) => i + 1)
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Review</h1>
          <p className="mt-1 text-sm text-muted">{due.length} due today</p>
        </div>
        <span className="text-sm text-muted tabular-nums">
          {index + 1} / {due.length}
        </span>
      </header>

      <div className="h-1.5 overflow-hidden rounded-full bg-line" aria-hidden>
        <div className="h-full bg-accent transition-all" style={{ width: `${(index / due.length) * 100}%` }} />
      </div>

      <div className="flex gap-2">
        <Badge>{topicTitles[item.topicId] ?? item.topicId}</Badge>
        <Badge>difficulty {item.difficulty}/5</Badge>
      </div>

      <QuestionCard key={item.id} item={item} title="Question" onChecked={setResult} />

      {result && <RatingButtons result={result} onRate={rate} />}
    </div>
  )
}
