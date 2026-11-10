import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { asApiError, type ApiError } from '../../../api/client'
import { listSharedSessions, type SharedSessionSummary } from '../../../api/sharedSessions'
import { useRole } from '../../../app/role'
import { ApiUnavailable } from '../../../components/ApiUnavailable'
import { Card } from '../../../components/ui'
import { formatDate } from '../../../lib/format'
import { UnitHeader } from '../UnitHeader'
import { useOffering } from '../useOffering'

/** Lecturer: sessions students chose to share with you, anonymously. */
export default function SharedSessionsView() {
  const offering = useOffering()
  const role = useRole()
  const [sessions, setSessions] = useState<SharedSessionSummary[] | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    if (role !== 'lecturer') return
    let cancelled = false
    listSharedSessions(offering.id)
      .then((s) => !cancelled && setSessions(s))
      .catch((e) => !cancelled && setError(asApiError(e)))
    return () => {
      cancelled = true
    }
  }, [offering.id, role])

  if (role !== 'lecturer') {
    return (
      <section className="mx-auto w-full max-w-3xl pb-10">
        <UnitHeader offering={offering} title="Shared sessions" />
        <p className="mt-4 text-muted">Only lecturers can see sessions students share.</p>
      </section>
    )
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 pb-10">
      <div>
        <UnitHeader offering={offering} title="Shared sessions" />
        <p className="mt-1 text-sm text-muted">
          Learning sessions students chose to share with you. They’re anonymous, and a session disappears from here the
          moment its student stops sharing.
        </p>
      </div>

      {error && <ApiUnavailable error={error} what="Shared sessions" />}

      {sessions?.length === 0 && (
        <Card>
          <p className="text-sm text-muted">No student has shared a session in this unit.</p>
        </Card>
      )}

      {sessions && sessions.length > 0 && (
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
          {sessions.map((s) => (
            <li key={s.shareId}>
              <Link to={s.shareId} className="block px-5 py-4 hover:bg-line/30">
                <p className="text-xs text-muted">
                  🕶 {s.studentLabel} · shared {formatDate(s.sharedAt)} · {s.messageCount} messages
                </p>
                <p className="mt-0.5 font-medium">{s.title}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
