import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { asApiError, type ApiError } from '../../../api/client'
import { approvePending, editVariant, getBank, setVariantStatus, type Bank, type VariantStatus } from '../../../api/srsBank'
import { useRole } from '../../../app/role'
import { ApiUnavailable } from '../../../components/ApiUnavailable'
import { Badge, Button, Card } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import { UnitHeader } from '../UnitHeader'
import { useOffering } from '../useOffering'
import { VariantRow } from './VariantRow'

type Filter = 'pending' | 'all'

/** Lecturer screen: check generated and live-rephrased questions before students see them. */
export default function QuestionsReviewView() {
  const offering = useOffering()
  const role = useRole()
  const [bank, setBank] = useState<Bank | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [filter, setFilter] = useState<Filter>('pending')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setBank(await getBank(offering.id))
      setError(null)
    } catch (e) {
      setError(asApiError(e))
    }
  }, [offering.id])

  useEffect(() => {
    if (role !== 'lecturer') return
    let cancelled = false
    getBank(offering.id)
      .then((b) => !cancelled && setBank(b))
      .catch((e) => !cancelled && setError(asApiError(e)))
    return () => {
      cancelled = true
    }
  }, [offering.id, role])

  if (role !== 'lecturer') {
    return (
      <section className="mx-auto w-full max-w-4xl pb-10">
        <UnitHeader offering={offering} title="Review questions" />
        <p className="mt-4 text-muted">Only lecturers can review questions.</p>
        <Link to={`/units/${offering.id}/practice`} className="mt-2 inline-block text-accent hover:underline">
          Go to Practice
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

  const pendingCount = bank?.items.reduce((n, i) => n + i.variants.filter((v) => v.status === 'pending').length, 0) ?? 0
  const items = (bank?.items ?? [])
    .map((i) => ({ ...i, shown: filter === 'all' ? i.variants : i.variants.filter((v) => v.status === 'pending') }))
    .filter((i) => i.shown.length > 0)

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 pb-10">
      <div>
        <UnitHeader offering={offering} title="Review questions" />
        <p className="mt-1 text-sm text-muted">
          Practice questions generated from your lectures, and rewordings written for students who struggled, wait here
          until you approve them. Students only ever see approved wordings.
        </p>
      </div>

      {error && error.status !== 403 && <ApiUnavailable error={error} what="Question review" onRetry={() => void load()} />}
      {error?.status === 403 && (
        <Card title="The API doesn’t recognise you as a lecturer">
          <p className="text-sm text-muted">
            The “Viewing as” switch only changes this page. Start the API with <code>ATHENA_DEV_LECTURER_ID=dev-lecturer</code>{' '}
            to act as a lecturer in development.
          </p>
        </Card>
      )}

      {bank && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div role="tablist" aria-label="Show" className="flex gap-1 rounded-lg bg-line/50 p-1">
              {(['pending', 'all'] as const).map((f) => (
                <button
                  key={f}
                  role="tab"
                  aria-selected={filter === f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    'rounded-md px-3 py-1 text-sm',
                    filter === f ? 'bg-surface font-medium shadow-sm' : 'text-muted hover:text-ink',
                  )}
                >
                  {f === 'pending' ? `Pending (${pendingCount})` : 'All questions'}
                </button>
              ))}
            </div>
            {pendingCount > 0 && (
              <Button size="sm" disabled={busy} onClick={() => void act(() => approvePending(offering.id))}>
                Approve all {pendingCount} pending
              </Button>
            )}
          </div>

          {items.length === 0 && (
            <Card>
              <p className="text-sm text-muted">
                {filter === 'pending' ? 'Nothing waiting for review.' : 'This unit has no questions yet.'}
              </p>
            </Card>
          )}

          {items.map((item) => (
            <section key={item.id} className="overflow-hidden rounded-xl border border-line bg-surface">
              <header className="space-y-1 border-b border-line px-5 py-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge tone="accent">{item.topic_id}</Badge>
                  <span className="text-muted">
                    difficulty {item.difficulty}/5 · {item.bloom}
                    {item.clip_ids.length > 0 && ` · from lecture clip ${item.clip_ids.join(', ')}`}
                  </span>
                </div>
                <h2 className="font-semibold">{item.concept}</h2>
              </header>
              <ol className="divide-y divide-line">
                {item.shown.map((v) => (
                  <VariantRow
                    key={v.id}
                    variant={v}
                    busy={busy}
                    onStatus={(status: VariantStatus) => void act(() => setVariantStatus(offering.id, item.id, v.id, status))}
                    onEdit={async (changes) => {
                      try {
                        await editVariant(offering.id, item.id, v.id, changes)
                        await load()
                        return null
                      } catch (e) {
                        return asApiError(e).message
                      }
                    }}
                  />
                ))}
              </ol>
            </section>
          ))}
        </>
      )}
    </div>
  )
}
