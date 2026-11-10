import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiUnavailable } from '../../../components/ApiUnavailable'
import { asApiError, type ApiError } from '../../../api/client'
import {
  getNextQuestion,
  rateAttempt,
  submitAnswer,
  type Rating,
  type SrsAttemptResult,
  type SrsNext,
} from '../../../api/srs'
import { Badge, Card } from '../../../components/ui'
import { listLectures } from '../../../api/lectures'
import { formatRelative } from '../../../lib/format'
import type { LectureRecording } from '../../../types'
import { openInPanel } from '../panel/panelStore'
import { studentView } from '../review/applyReview'
import { useDecisions } from '../review/reviewStore'
import { suggestClips } from './clipSuggestions'
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
    return { phase: 'error', error: asApiError(e) }
  }
}

/** Spaced repetition for one unit: due reviews first, then a few new questions a day. */
export default function PracticeView() {
  const offering = useOffering()
  const [state, setState] = useState<State>({ phase: 'loading' })
  const [busy, setBusy] = useState(false)
  const [tally, setTally] = useState({ answered: 0, right: 0 })
  const [lectures, setLectures] = useState<LectureRecording[]>([])
  const decisions = useDecisions()

  // The unit's clips, as students see them (approved only), for "rewatch" suggestions.
  useEffect(() => {
    let cancelled = false
    void listLectures(offering.id).then((l) => !cancelled && setLectures(l))
    return () => {
      cancelled = true
    }
  }, [offering.id])
  const visible = useMemo(() => lectures.map((l) => studentView(l, decisions)), [lectures, decisions])

  const suggestions =
    state.phase === 'question' && state.result
      ? suggestClips(visible, {
          clipIds: state.result.feedback.clip_ids,
          topicId: state.next.topic_id,
          text: `${state.next.question.stem} ${state.result.feedback.explanation}`,
        })
      : []

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
      setState({ phase: 'error', error: asApiError(e) })
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
      setState({ phase: 'error', error: asApiError(e) })
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

      {state.phase === 'error' && <ApiUnavailable error={state.error} what="Practice" onRetry={() => void load()} />}

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
              <FeedbackPanel
                result={state.result}
                suggestions={suggestions}
                onWatch={(sg) => openInPanel(offering.id, { kind: 'clip', clip: sg.clip, lecture: sg.lecture })}
                busy={busy}
                onRate={(r) => void rate(r)}
                onNext={() => void load()}
              />
            )}
          </Card>
        </>
      )}
    </div>
  )
}
