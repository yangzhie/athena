import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  getNextQuestion,
  rateAttempt,
  submitAnswer,
  type Rating,
  type SrsAttemptResult,
  type SrsNext,
} from '../../../api/srs'
import { Badge, Button, Card } from '../../../components/ui'
import { formatRelative } from '../../../lib/format'
import { UnitHeader } from '../UnitHeader'
import { useOffering } from '../useOffering'
import { FeedbackPanel } from './FeedbackPanel'
import { QuestionForm } from './QuestionForm'
import { refreshSrsSummary } from './summaryStore'

type State =
  | { phase: 'loading' }
  | { phase: 'error'; error: ApiError }
  | { phase: 'question'; next: Extract<SrsNext, { done: false }>; result: SrsAttemptResult | null }
  | { phase: 'done'; nextDueAt: string | null }

/** The next question (or done/error), and refresh the sidebar's due badge. */
async function fetchState(offeringId: string): Promise<State> {
  void refreshSrsSummary(offeringId)
  try {
    const next = await getNextQuestion(offeringId)
    return next.done ? { phase: 'done', nextDueAt: next.next_due_at } : { phase: 'question', next, result: null }
  } catch (e) {
    return { phase: 'error', error: e instanceof ApiError ? e : new ApiError(0, String(e)) }
  }
}

/** Spaced repetition for one unit: due reviews first, then a few new questions a day. */
export default function PracticeView() {
  const offering = useOffering()
  const [state, setState] = useState<State>({ phase: 'loading' })
  const [busy, setBusy] = useState(false)
  const [tally, setTally] = useState({ answered: 0, right: 0 })

  const load = useCallback(async () => {
    setState(await fetchState(offering.id))
  }, [offering.id])

  useEffect(() => {
    let cancelled = false
    void fetchState(offering.id).then((next) => {
      if (!cancelled) setState(next)
    })
    return () => {
      cancelled = true
    }
  }, [offering.id])

  async function answer(value: number | string | null) {
    if (state.phase !== 'question') return
    setBusy(true)
    try {
      const result = await submitAnswer(offering.id, state.next.item_id, state.next.question.variant_id, value)
      setState({ ...state, result })
      setTally((t) => ({ answered: t.answered + 1, right: t.right + (result.correct === true ? 1 : 0) }))
      if (!result.needs_rating) void refreshSrsSummary(offering.id)
    } catch (e) {
      setState({ phase: 'error', error: e instanceof ApiError ? e : new ApiError(0, String(e)) })
    } finally {
      setBusy(false)
    }
  }

  async function rate(rating: Rating) {
    if (state.phase !== 'question' || !state.result) return
    setBusy(true)
    try {
      await rateAttempt(offering.id, state.result.attempt_id, rating)
      await load()
    } catch (e) {
      setState({ phase: 'error', error: e instanceof ApiError ? e : new ApiError(0, String(e)) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl space-y-5 pb-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <UnitHeader offering={offering} title="Practice" />
          <p className="mt-1 text-sm text-muted">Spaced repetition: questions come back just before you’d forget them.</p>
        </div>
        {tally.answered > 0 && (
          <span className="text-sm text-muted tabular-nums">
            {tally.right}/{tally.answered} right this session
          </span>
        )}
      </div>

      {state.phase === 'loading' && <Card>Loading…</Card>}

      {state.phase === 'error' && (
        <Card title={state.error.status === 0 ? 'Practice isn’t available' : 'Something went wrong'}>
          <p className="text-sm text-muted">{state.error.message}</p>
          {state.error.status === 0 && (
            <pre className="mt-3 overflow-x-auto rounded-lg bg-line/40 p-3 text-xs">
              {'cd apps/api\nuv run athena-srs load-starter\nATHENA_DEV_STUDENT_ID=dev-student uv run uvicorn athena_api.app:create_app --factory --reload'}
            </pre>
          )}
          <Button variant="secondary" size="sm" className="mt-3" onClick={() => void load()}>
            Try again
          </Button>
        </Card>
      )}

      {state.phase === 'done' && (
        <Card>
          <h2 className="text-lg font-semibold">All done for now</h2>
          <p className="mt-1 text-sm text-muted">
            {state.nextDueAt
              ? `Your next review is due ${formatRelative(state.nextDueAt)}.`
              : 'Nothing is scheduled yet. New questions unlock each day.'}
          </p>
        </Card>
      )}

      {state.phase === 'question' && (
        <>
          <div className="flex flex-wrap gap-2">
            {state.next.is_new ? <Badge tone="accent">New</Badge> : <Badge>Review</Badge>}
            <Badge>{state.next.remaining.due} due</Badge>
            <Badge>{state.next.remaining.new} new left today</Badge>
          </div>
          <Card>
            <QuestionForm
              key={state.next.question.variant_id + state.next.item_id}
              question={state.next.question}
              feedback={state.result?.feedback ?? null}
              correct={state.result?.correct}
              busy={busy}
              onSubmit={(v) => void answer(v)}
            />
            {state.result && (
              <FeedbackPanel result={state.result} busy={busy} onRate={(r) => void rate(r)} onNext={() => void load()} />
            )}
          </Card>
        </>
      )}
    </div>
  )
}
