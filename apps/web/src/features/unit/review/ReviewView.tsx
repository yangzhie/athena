import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { asApiError, type ApiError } from '../../../api/client'
import {
  approvePendingClips,
  editClip,
  getLecturesForReview,
  resetClip,
  setClipStatus,
} from '../../../api/lectureReview'
import { useRole } from '../../../app/role'
import { ApiUnavailable } from '../../../components/ApiUnavailable'
import { Badge, Button, Card } from '../../../components/ui'
import { formatTimestamp } from '../../../lib/format'
import { openInPanel } from '../panel/panelStore'
import { UnitHeader } from '../UnitHeader'
import { useOffering } from '../useOffering'
import { ReviewClipRow } from './ReviewClipRow'
import { ReviewTimeline } from './ReviewTimeline'
import type { ReviewedLecture } from './types'

/** Lecturer screen: check the clips lecture indexing proposed before students (and the tutor) use them. */
export default function ReviewView() {
  const offering = useOffering()
  const role = useRole()
  const [lectures, setLectures] = useState<ReviewedLecture[] | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setLectures(await getLecturesForReview(offering.id))
      setError(null)
    } catch (e) {
      setError(asApiError(e))
    }
  }, [offering.id])

  useEffect(() => {
    if (role !== 'lecturer') return
    let cancelled = false
    getLecturesForReview(offering.id)
      .then((l) => !cancelled && setLectures(l))
      .catch((e) => !cancelled && setError(asApiError(e)))
    return () => {
      cancelled = true
    }
  }, [offering.id, role])

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

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    try {
      await fn()
      await load()
    } catch (e) {
      setError(asApiError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 pb-10">
      <div>
        <UnitHeader offering={offering} title="Review clips" />
        <p className="mt-1 text-sm text-muted">
          Lecture indexing proposes clips. Students, and the tutor in their sessions, only use the ones you approve.
        </p>
      </div>

      {error && error.status !== 403 && <ApiUnavailable error={error} what="Clip review" onRetry={() => void load()} />}
      {error?.status === 403 && (
        <Card title="The API doesn’t recognise you as a lecturer">
          <p className="text-sm text-muted">
            Lecturer access requires a server-issued invite and management permission for this Offering.
          </p>
        </Card>
      )}

      {lectures?.length === 0 && (
        <Card>
          <p className="text-sm text-muted">
            No indexed lectures for this unit yet. Index a recording with <code>workers/indexer</code>, then import it
            with <code>uv run athena-lectures import &lt;clips.json&gt;</code> in <code>apps/api</code>.
          </p>
        </Card>
      )}

      {lectures?.map((lecture) => {
        const clips = [...lecture.clips].sort((a, b) => a.startS - b.startS)
        const pending = clips.filter((c) => c.status === 'pending').length
        const approved = clips.filter((c) => c.status === 'approved').length
        const active = clips.filter((c) => c.status !== 'rejected')

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
                  {pending > 0 ? (
                    <Button size="sm" disabled={busy} onClick={() => void act(() => approvePendingClips(offering.id, lecture.id))}>
                      Approve {pending} pending
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
                {clips.map((c) => {
                  const i = active.findIndex((a) => a.id === c.id)
                  return (
                    <ReviewClipRow
                      key={c.id}
                      clip={c}
                      durationS={lecture.durationS}
                      prevEndS={i > 0 ? active[i - 1].endS : 0}
                      nextStartS={i >= 0 && i < active.length - 1 ? active[i + 1].startS : lecture.durationS}
                      busy={busy}
                      onPreview={() => openInPanel(offering.id, { kind: 'clip', clip: c, lecture })}
                      onStatus={(status) => void act(() => setClipStatus(offering.id, lecture.id, c.id, status))}
                      onReset={() => void act(() => resetClip(offering.id, lecture.id, c.id))}
                      onEdit={async (edit) => {
                        try {
                          await editClip(offering.id, lecture.id, c.id, edit)
                          await load()
                          return null
                        } catch (e) {
                          return asApiError(e).message
                        }
                      }}
                    />
                  )
                })}
              </ol>
            )}
          </section>
        )
      })}
    </div>
  )
}
