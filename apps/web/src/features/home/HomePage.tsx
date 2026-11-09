import { useState, type FormEvent } from 'react'
import { Link, useLoaderData } from 'react-router'
import { Badge, Button, Card, MasteryBar, buttonStyles } from '../../components/ui'
import type { homeLoader } from './loader'

export default function HomePage() {
  const { topics } = useLoaderData<typeof homeLoader>()
  const [query, setQuery] = useState('')

  function startTopic(e: FormEvent) {
    e.preventDefault()
    // Static for now: creating a topic needs the backend.
  }

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <section>
        <h1 className="text-3xl font-semibold tracking-tight">What do you want to learn?</h1>
        <p className="mt-2 text-muted">
          Name a topic, big or small. Athena will check what you already know and take it from there.
        </p>
        <form onSubmit={startTopic} className="mt-5 flex flex-col gap-2 sm:flex-row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. Bubble sort, Machine learning, Organic chemistry"
            aria-label="Topic to learn"
            className="h-10 flex-1 rounded-lg border border-line bg-surface px-3 text-sm outline-none focus:border-accent"
          />
          <Button type="submit" disabled={!query.trim()}>
            Start learning
          </Button>
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Continue learning</h2>
        {topics.length === 0 ? (
          <p className="text-muted">No topics yet. Start one above.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {topics.map((topic) => (
              <Card
                key={topic.id}
                title={topic.title}
                action={<Badge tone={topic.scope === 'broad' ? 'accent' : 'neutral'}>{topic.scope}</Badge>}
                className="flex flex-col"
              >
                <p className="text-sm text-muted">{topic.description}</p>
                <MasteryBar label="Mastery" value={topic.mastery} className="mt-4" />
                <Link to={`/learn/${topic.id}`} className={buttonStyles('secondary', 'sm', 'mt-4 self-start')}>
                  Continue
                </Link>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
