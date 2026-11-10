import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { asApiError, type ApiError } from '../../../api/client'
import { getSharedSession, type SharedSessionSummary } from '../../../api/sharedSessions'
import { useRole } from '../../../app/role'
import { ApiUnavailable } from '../../../components/ApiUnavailable'
import { Card } from '../../../components/ui'
import { formatDate } from '../../../lib/format'
import type { ChatMessage } from '../../../types'
import { MessageBubble } from '../chat/MessageBubble'
import { useOffering } from '../useOffering'

/** Lecturer: one shared session, anonymous and read-only (replies come next). */
export default function SharedSessionView() {
  const offering = useOffering()
  const role = useRole()
  const { shareId = '' } = useParams()
  const [data, setData] = useState<{ session: SharedSessionSummary; messages: ChatMessage[] } | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    if (role !== 'lecturer') return
    let cancelled = false
    getSharedSession(offering.id, shareId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(asApiError(e)))
    return () => {
      cancelled = true
    }
  }, [offering.id, shareId, role])

  const back = (
    <Link to={`/units/${offering.id}/shared`} className="text-sm text-accent hover:underline">
      ← Shared sessions
    </Link>
  )

  if (role !== 'lecturer') return <p className="mx-auto max-w-3xl text-muted">Only lecturers can see shared sessions.</p>
  if (error?.status === 404) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-3">
        {back}
        <Card title="No longer shared">
          <p className="text-sm text-muted">The student stopped sharing this session, so it’s no longer available.</p>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 pb-10">
      {back}
      {error && <ApiUnavailable error={error} what="This shared session" />}
      {data && (
        <>
          <header>
            <p className="text-sm text-muted">
              🕶 {data.session.studentLabel} · shared {formatDate(data.session.sharedAt)}
            </p>
            <h1 className="mt-0.5 text-xl font-semibold tracking-tight">{data.session.title}</h1>
          </header>
          <div className="space-y-6">
            {data.messages.map((m) => (
              <MessageBubble key={m.id} message={m} offeringId={offering.id} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
