import { Link, useLoaderData } from 'react-router'
import { Badge } from '../../components/ui'
import type { learnIndexLoader } from './loader'

export default function LearnIndexPage() {
  const { topics } = useLoaderData<typeof learnIndexLoader>()
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">Pick a topic</h1>
      <ul className="mt-5 divide-y divide-line rounded-xl border border-line bg-surface">
        {topics.map((t) => (
          <li key={t.id}>
            <Link to={t.id} className="flex items-center justify-between gap-3 px-5 py-4 hover:bg-line/30">
              <span className="font-medium">{t.title}</span>
              <Badge tone={t.scope === 'broad' ? 'accent' : 'neutral'}>{t.scope}</Badge>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
