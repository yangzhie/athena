import { Link, useLoaderData } from 'react-router'
import { Card, MasteryBar } from '../../components/ui'
import { StatTile } from './components/StatTile'
import type { progressLoader } from './loader'

export default function ProgressPage() {
  const { total, counts, ready, blocked, topics } = useLoaderData<typeof progressLoader>()

  return (
    <div className="mx-auto max-w-5xl space-y-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Progress</h1>
        <p className="mt-1 text-muted">What Athena thinks you know, concept by concept.</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Concept summary">
        <StatTile level="mastered" value={counts.mastered} total={total} />
        <StatTile level="learning" value={counts.learning} total={total} />
        <StatTile level="gap" value={counts.gap} total={total} />
      </section>

      <div className="grid gap-8 lg:grid-cols-[1fr_20rem]">
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">By topic</h2>
          {topics.map((t) => (
            <Card
              key={t.id}
              title={t.title}
              action={
                <Link to={`/learn/${t.id}`} className="text-sm text-accent hover:underline">
                  Continue
                </Link>
              }
            >
              <div className="space-y-3">
                {t.concepts.map((c) => (
                  <MasteryBar key={c.id} label={c.name} value={c.mastery} />
                ))}
              </div>
            </Card>
          ))}
        </section>

        <aside className="space-y-4">
          <h2 className="text-lg font-semibold">Next up</h2>
          <Card>
            {ready.length === 0 ? (
              <p className="text-sm text-muted">Everything you can work on is mastered.</p>
            ) : (
              <ul className="space-y-3">
                {ready.map((c) => (
                  <li key={c.id}>
                    <MasteryBar label={c.name} value={c.mastery} />
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {blocked.length > 0 && (
            <Card title="Unlocks later">
              <ul className="space-y-2 text-sm">
                {blocked.map((c) => (
                  <li key={c.id}>
                    <span className="font-medium">{c.name}</span>
                    <span className="text-muted"> · needs {c.blockedBy.join(', ')}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </aside>
      </div>
    </div>
  )
}
