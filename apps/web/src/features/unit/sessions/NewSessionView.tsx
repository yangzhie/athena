import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { hasPendingSession } from '../../../api/sessions'
import { useRole } from '../../../app/role'
import { ApiUnavailable } from '../../../components/ApiUnavailable'
import { Button, Card } from '../../../components/ui'
import { formatDate } from '../../../lib/format'
import { UnitHeader } from '../UnitHeader'
import { useOffering } from '../useOffering'
import { useGoalPlaceholder } from './goalExample'
import { createSession, recoverSession, refreshSessions, useSessionList } from './sessionStore'

/** The unit's landing page: start a new learning session, or reopen one. */
export default function NewSessionView() {
  const offering = useOffering()
  const role = useRole()
  const { status, sessions, error } = useSessionList(offering.id)
  const navigate = useNavigate()
  const [goal, setGoal] = useState('')
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const pending = hasPendingSession(offering.id)
  const placeholder = useGoalPlaceholder(offering.id, offering.unit.title)

  useEffect(() => {
    if (role === 'student') void refreshSessions(offering.id)
  }, [offering.id, role])

  if (role === 'lecturer') {
    return (
      <div className="mx-auto w-full max-w-2xl space-y-6 pb-10">
        <UnitHeader offering={offering} />
        <Card title="Students’ learning sessions are private">
          <p className="text-sm text-muted">
            Each student’s sessions and chats are visible only to them, unless they choose to share one with you
            (anonymously).
          </p>
          <Link to={`/units/${offering.id}/shared`} className="mt-3 inline-block text-sm text-accent hover:underline">
            See shared sessions
          </Link>
        </Card>
      </div>
    )
  }

  async function start(text: string) {
    if (!text.trim() || starting) return
    setStarting(true)
    setStartError(null)
    try {
      const session = await createSession(offering.id, text)
      navigate(`/units/${offering.id}/s/${session.id}`)
    } catch (e) {
      setStartError(e instanceof Error ? e.message : 'Couldn’t start the session.')
      setStarting(false)
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    void start(goal)
  }

  async function recover() {
    if (starting) return
    setStarting(true)
    setStartError(null)
    try {
      const session = await recoverSession(offering.id)
      if (session) navigate(`/units/${offering.id}/s/${session.id}`)
    } catch (e) {
      setStartError(e instanceof Error ? e.message : 'Couldn’t recover the session.')
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl space-y-10 pb-10">
      <div>
        <UnitHeader offering={offering} />
        <h2 className="mt-8 text-2xl font-semibold tracking-tight">What do you want to learn?</h2>
        <p className="mt-1 text-muted">
          Start a session for one thing, like a topic, a confusing idea or an exam question. Each session is its own
          chat.
        </p>
        <form onSubmit={submit} className="mt-5 flex flex-col gap-2 sm:flex-row">
          <input
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder={placeholder}
            aria-label="What do you want to learn?"
            maxLength={200}
            className="h-11 flex-1 rounded-xl border border-line bg-surface px-4 text-sm outline-none focus:border-accent"
          />
          <Button type="submit" disabled={!goal.trim() || starting || pending} className="h-11">
            {starting ? 'Starting…' : 'Start session'}
          </Button>
        </form>
        {starting && <p className="mt-2 text-sm text-muted" role="status">
          Preparing a focused plan and first question. Checking course sources can take a little longer.
        </p>}
        {pending && !starting && (
          <div className="mt-3 space-y-2" role="status">
            <p className="text-sm text-muted">
              Your previous session request has not been confirmed. Recover it before starting another session to avoid duplicates.
            </p>
            <Button onClick={() => void recover()}>Recover previous session</Button>
          </div>
        )}
        {startError && (
          <p className="mt-2 text-sm text-bad" role="alert">
            {startError}
          </p>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          {offering.suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => void start(s)}
              disabled={starting || pending}
              className="rounded-full border border-line bg-surface px-3 py-1.5 text-sm transition-colors hover:bg-line/50"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {status === 'error' && error && (
        <ApiUnavailable error={error} what="Sessions" onRetry={() => void refreshSessions(offering.id)} />
      )}

      {sessions.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-medium text-muted">Your sessions</h2>
          <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
            {sessions.map((s) => (
              <li key={s.id}>
                <Link
                  to={`/units/${offering.id}/s/${s.id}`}
                  className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-line/30"
                >
                  <span className="truncate font-medium">{s.title}</span>
                  <span className="shrink-0 text-xs text-muted">{formatDate(s.updatedAt)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
