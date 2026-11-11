import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { hasPendingSession } from '../../../api/sessions'
import { useRole } from '../../../app/role'
import { ApiUnavailable } from '../../../components/ApiUnavailable'
import { Button, Card, Icon, type IconName } from '../../../components/ui'
import { listCourseTopics } from '../../../api/progress'
import { unitColor } from '../../../lib/unitColor'
import { refreshSrsSummary, useSrsSummary } from '../practice/summaryStore'
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
  const summary = useSrsSummary(offering.id)
  const [topics, setTopics] = useState<string[]>([])

  useEffect(() => {
    if (role !== 'student') return
    void refreshSessions(offering.id)
    void refreshSrsSummary(offering.id)
    let active = true
    listCourseTopics(offering.id).then((t) => { if (active) setTopics(t.map((x) => x.title)) }).catch(() => {})
    return () => { active = false }
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

  const due = summary ? summary.due_now + summary.new_available : 0
  const starters = [...new Set([...offering.suggestions, ...topics])]

  return (
    <div className="mx-auto w-full max-w-3xl space-y-12 pt-2 pb-12" style={{ '--unit': unitColor(offering.unit.code) } as CSSProperties}>
      <div>
        <p className="text-xs font-semibold tracking-[0.14em] uppercase">
          <span className="text-(--unit)">{offering.unit.code}</span>
          <span className="text-muted"> · {offering.semester} {offering.year}</span>
        </p>
        <h1 className="mt-1 text-4xl leading-tight font-semibold">{offering.unit.title}</h1>

        {/* The prompt, written on the page's ruled line. */}
        <form onSubmit={submit} className="mt-10">
          <label htmlFor="goal" className="font-serif text-xl font-medium">What do you want to learn today?</label>
          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
            <input
              id="goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder={placeholder}
              maxLength={200}
              className="h-12 flex-1 border-b-2 border-line bg-transparent px-1 font-serif text-xl outline-none placeholder:text-muted/70 placeholder:italic focus:border-accent"
            />
            <Button type="submit" disabled={!goal.trim() || starting || pending} className="h-11 px-5">
              {starting ? 'Preparing…' : 'Begin lesson →'}
            </Button>
          </div>
        </form>
        <p className="mt-3 text-sm text-muted">
          One lesson per thing you want to understand: a topic, a confusing idea or an exam question. The tutor checks
          what you already know first, then teaches only what you need.
        </p>
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
      </div>

      {starters.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold">Or start from a topic</h2>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {starters.map((s, i) => (
              <li key={s}>
                <button
                  type="button"
                  onClick={() => void start(s)}
                  disabled={starting || pending}
                  className="group flex w-full items-baseline gap-3 rounded-md border border-line bg-surface px-4 py-3 text-left transition-colors hover:border-(--unit) disabled:opacity-60"
                >
                  <span className="font-serif text-sm font-semibold text-(--unit) tabular-nums">{String(i + 1).padStart(2, '0')}</span>
                  <span className="flex-1 group-hover:underline">{s}</span>
                  <span aria-hidden className="text-muted transition-transform group-hover:translate-x-0.5">→</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {status === 'error' && error && (
        <ApiUnavailable error={error} what="Sessions" onRetry={() => void refreshSessions(offering.id)} />
      )}

      {sessions.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold">Your lessons</h2>
          {/* A table of contents: title, dotted leader, date. */}
          <ol className="mt-3">
            {sessions.map((s) => (
              <li key={s.id}>
                <Link
                  to={`/units/${offering.id}/s/${s.id}`}
                  className="group flex items-baseline gap-2 py-2"
                >
                  <span className="truncate font-serif text-[1.05rem] group-hover:text-accent group-hover:underline">{s.title}</span>
                  {s.shared && <span className="shrink-0 text-xs text-muted">(shared)</span>}
                  <span aria-hidden className="min-w-6 flex-1 translate-y-[-0.2em] border-b-2 border-dotted border-line" />
                  <span className="shrink-0 text-sm text-muted tabular-nums">{formatDate(s.updatedAt)}</span>
                </Link>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="grid gap-3 sm:grid-cols-3">
        <UnitLink to={`/units/${offering.id}/practice`} icon="cards" title="Practice"
          detail={due > 0 ? `${due} ready to review` : 'Spaced review of what you’ve learned'} badge={due > 0 ? due : undefined} />
        <UnitLink to={`/units/${offering.id}/clips`} icon="film" title="Lecture clips" detail="Recordings split by topic" />
        <UnitLink to={`/units/${offering.id}/library`} icon="book" title="Material library" detail="Notes and slides for this unit" />
      </section>
    </div>
  )
}

function UnitLink({ to, icon, title, detail, badge }: { to: string; icon: IconName; title: string; detail: string; badge?: number }) {
  return (
    <Link to={to} className="group rounded-md border border-line bg-surface p-4 transition-colors hover:border-accent">
      <span className="flex items-center gap-2">
        <Icon name={icon} className="text-accent" />
        <span className="font-serif font-semibold group-hover:underline">{title}</span>
        {badge !== undefined && <span className="ml-auto rounded-full bg-margin px-1.5 text-xs font-semibold text-surface tabular-nums">{badge}</span>}
      </span>
      <span className="mt-1 block text-sm text-muted">{detail}</span>
    </Link>
  )
}
