import { Link, useLoaderData } from 'react-router'
import { useRole } from '../../../app/role'
import { Badge, Button } from '../../../components/ui'
import { formatTimestamp } from '../../../lib/format'
import type { clipsLoader } from '../loader'
import { openInPanel } from '../panel/panelStore'
import { UnitHeader } from '../UnitHeader'
import { useOffering } from '../useOffering'
import { reviewClip } from './applyReview'
import { ReviewClipRow } from './ReviewClipRow'
import { ReviewTimeline } from './ReviewTimeline'
import { approveAll, useDecisions } from './reviewStore'

/** Lecturer screen: check the clips lecture indexing proposed before students see them. */
export default function ReviewView() {
  const offering = useOffering()
  const role = useRole()
  const { lectures } = useLoaderData<typeof clipsLoader>()
  const decisions = useDecisions()

  if (role !== 'lecturer') {
    return (
      <section className="mx-auto w-full max-w-4xl pb-10">
        <UnitHeader offering={offering} title="Review clips" />
        <p className="mt-4 text-muted">Only lecturers can review lecture clips.</p>
        <Link to={`/units/${offering.id}/clips`} className="mt-2 inline-block text-accent hover:underline">
          See the approved clips
        </Link>
      </section>
    )
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 pb-10">
      <div>
        <UnitHeader offering={offering} title="Review clips" />
        <p className="mt-1 text-sm text-muted">
          Lecture indexing proposes clips. Students only see the ones you approve. Your decisions are saved in this
          browser for now.
        </p>
      </div>

      {lectures.length === 0 && (
        <p className="rounded-xl border-2 border-dashed border-line p-10 text-center text-muted">No lectures yet.</p>
      )}

      {lectures.map((lecture) => {
        const clips = lecture.clips.map((c) => reviewClip(c, decisions[c.id])).sort((a, b) => a.startS - b.startS)
        const pending = clips.filter((c) => c.status === 'pending')
        const approved = clips.filter((c) => c.status === 'approved').length

        return (
          <section key={lecture.id} className="overflow-hidden rounded-xl border border-line bg-surface">
            <header className="space-y-3 border-b border-line px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold">
                  {lecture.week > 0 && `Week ${lecture.week} · `}
                  {lecture.title}
                </h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted">
                    {approved}/{clips.length} approved · {formatTimestamp(lecture.durationS)}
                  </span>
                  {pending.length > 0 ? (
                    <Button size="sm" onClick={() => approveAll(pending.map((c) => c.id))}>
                      Approve {pending.length} pending
                    </Button>
                  ) : (
                    clips.length > 0 && <Badge tone="good">✓ Reviewed</Badge>
                  )}
                </div>
              </div>
              {clips.length > 0 && <ReviewTimeline clips={clips} durationS={lecture.durationS} />}
            </header>

            {clips.length === 0 ? (
              <p className="px-5 py-4 text-sm text-muted">
                {lecture.status === 'processing' ? 'Still being indexed.' : 'No clips were proposed.'}
              </p>
            ) : (
              <ol className="divide-y divide-line">
                {clips.map((c, i) => (
                  <ReviewClipRow
                    key={c.id}
                    clip={c}
                    durationS={lecture.durationS}
                    prevEndS={i > 0 ? clips[i - 1].endS : 0}
                    nextStartS={i < clips.length - 1 ? clips[i + 1].startS : lecture.durationS}
                    onPreview={() => openInPanel(offering.id, { kind: 'clip', clip: c, lecture })}
                  />
                ))}
              </ol>
            )}
          </section>
        )
      })}
    </div>
  )
}
