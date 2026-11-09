import { useLoaderData } from 'react-router'
import { Badge } from '../../../components/ui'
import { formatTimestamp } from '../../../lib/format'
import type { clipsLoader } from '../loader'
import { UnitHeader } from '../UnitHeader'
import { useOffering } from '../useOffering'
import { ClipRow } from './ClipRow'

/** The unit's lecture clips: recordings split by topic by lecture indexing, newest week first. */
export default function ClipsView() {
  const offering = useOffering()
  const { lectures } = useLoaderData<typeof clipsLoader>()
  const clipCount = lectures.reduce((n, l) => n + l.clips.length, 0)

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 pb-10">
      <div>
        <UnitHeader offering={offering} title="Lecture clips" />
        <p className="mt-1 text-sm text-muted">
          {clipCount} clip{clipCount === 1 ? '' : 's'} from {lectures.length} lecture
          {lectures.length === 1 ? '' : 's'}, split by topic.
        </p>
      </div>

      {lectures.length === 0 ? (
        <p className="rounded-xl border-2 border-dashed border-line p-10 text-center text-muted">
          No lectures yet. Clips appear here once your lecturer uploads recordings.
        </p>
      ) : (
        lectures.map((lecture) => (
          <section key={lecture.id} className="overflow-hidden rounded-xl border border-line bg-surface">
            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3">
              <h2 className="font-semibold">
                Week {lecture.week} · {lecture.title}
              </h2>
              <span className="flex items-center gap-2 text-xs text-muted">
                {formatTimestamp(lecture.durationS)}
                {lecture.status !== 'ready' && (
                  <Badge tone={lecture.status === 'failed' ? 'bad' : 'warn'}>{lecture.status}</Badge>
                )}
              </span>
            </header>
            {lecture.clips.length === 0 ? (
              <p className="px-5 py-4 text-sm text-muted">
                {lecture.status === 'processing'
                  ? 'Being split into clips. Check back soon.'
                  : 'No approved clips yet.'}
              </p>
            ) : (
              <ol className="divide-y divide-line">
                {lecture.clips.map((c) => (
                  <ClipRow key={c.id} clip={c} />
                ))}
              </ol>
            )}
          </section>
        ))
      )}
    </div>
  )
}
