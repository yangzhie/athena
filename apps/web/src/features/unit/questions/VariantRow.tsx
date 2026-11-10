import { useState } from 'react'
import type { BankVariant, VariantOrigin, VariantStatus } from '../../../api/srsBank'
import { Badge, Button, type Tone } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import { VariantEditor } from './VariantEditor'

const statusMeta: Record<VariantStatus, { label: string; icon: string; tone: Tone }> = {
  approved: { label: 'Approved', icon: '✓', tone: 'good' },
  pending: { label: 'Pending', icon: '◐', tone: 'warn' },
  rejected: { label: 'Rejected', icon: '✕', tone: 'neutral' },
}

const originLabel: Record<VariantOrigin, string> = {
  bank: 'Starter',
  generated: 'Generated from lecture',
  live: 'Live rephrase',
}

interface Props {
  variant: BankVariant
  busy: boolean
  onStatus: (status: VariantStatus) => void
  onEdit: (changes: Record<string, unknown>) => Promise<string | null>
}

/** One wording: question, answer, explanation, and the lecturer's actions. */
export function VariantRow({ variant: v, busy, onStatus, onEdit }: Props) {
  const [editing, setEditing] = useState(false)
  const s = statusMeta[v.status]

  return (
    <li className={cn('px-5 py-4', v.status === 'rejected' && 'opacity-60')}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <Badge tone={s.tone}>
          <span aria-hidden>{s.icon}</span>&nbsp;{s.label}
        </Badge>
        <Badge tone={v.origin === 'bank' ? 'neutral' : 'accent'}>{originLabel[v.origin]}</Badge>
        <span className="text-muted">{v.kind === 'mcq' ? 'Multiple choice' : v.kind === 'numeric' ? 'Numeric' : 'Short answer'}</span>
      </div>

      {editing ? (
        <VariantEditor
          variant={v}
          onCancel={() => setEditing(false)}
          onSave={async (changes) => {
            const error = await onEdit(changes)
            if (!error) setEditing(false)
            return error
          }}
        />
      ) : (
        <>
          <p className="font-medium">{v.stem}</p>
          {v.kind === 'mcq' && (
            <ul className="mt-2 space-y-1 text-sm">
              {v.options.map((o, i) => (
                <li key={o} className={cn('flex gap-2', i === v.answer_index ? 'text-good' : 'text-muted')}>
                  <span aria-hidden>{i === v.answer_index ? '✓' : '·'}</span>
                  <span className="font-mono">{o}</span>
                  {i === v.answer_index && <span className="sr-only">(correct)</span>}
                </li>
              ))}
            </ul>
          )}
          {v.kind === 'numeric' && (
            <p className="mt-2 text-sm">
              Answer: <span className="font-mono">{v.answer}</span>
              {v.tolerance > 0 && <span className="text-muted"> (± {v.tolerance})</span>}
            </p>
          )}
          {v.kind === 'short' && (
            <div className="mt-2 text-sm">
              <p>
                <span className="text-muted">Model answer: </span>
                {v.model_answer}
              </p>
              <ul className="mt-1 list-disc pl-5 text-muted">
                {v.rubric.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-2 text-sm text-muted">{v.explanation}</p>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {v.status !== 'approved' && (
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => onStatus('approved')}>
                Approve
              </Button>
            )}
            {v.status !== 'rejected' && (
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => onStatus('rejected')}>
                Reject
              </Button>
            )}
            {v.status === 'rejected' && (
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => onStatus('pending')}>
                Undo reject
              </Button>
            )}
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setEditing(true)}>
              Edit
            </Button>
          </div>
        </>
      )}
    </li>
  )
}
