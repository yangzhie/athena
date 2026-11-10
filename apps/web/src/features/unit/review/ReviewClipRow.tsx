import { useState, type FormEvent } from 'react'
import { Badge, Button, type Tone } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import { formatTimestamp, parseTimestamp } from '../../../lib/format'
import type { ReviewedClip, ReviewStatus } from './types'

const statusMeta: Record<ReviewStatus, { label: string; icon: string; tone: Tone }> = {
  approved: { label: 'Approved', icon: '✓', tone: 'good' },
  rejected: { label: 'Rejected', icon: '✕', tone: 'neutral' },
  pending: { label: 'Pending', icon: '◐', tone: 'warn' },
}

const field = 'h-8 rounded-md border border-line bg-surface px-2 text-sm outline-none focus:border-accent'

interface Props {
  clip: ReviewedClip
  durationS: number
  /** Neighbouring clips' bounds, so edits can't overlap them. */
  prevEndS: number
  nextStartS: number
  busy: boolean
  onPreview: () => void
  onStatus: (status: ReviewStatus) => void
  onReset: () => void
  /** Returns an error message, or null when saved. */
  onEdit: (edit: { title: string; startS: number; endS: number }) => Promise<string | null>
}

export function ReviewClipRow({ clip, durationS, prevEndS, nextStartS, busy, onPreview, onStatus, onReset, onEdit }: Props) {
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const meta = statusMeta[clip.status]
  const edited =
    clip.title !== clip.original.title || clip.startS !== clip.original.startS || clip.endS !== clip.original.endS

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    const title = String(data.get('title')).trim()
    const startS = parseTimestamp(String(data.get('start')))
    const endS = parseTimestamp(String(data.get('end')))
    if (!title) return setError('Give the clip a title.')
    if (startS === null || endS === null) return setError('Use times like 12:30 or 1:02:05.')
    if (endS <= startS) return setError('The end must be after the start.')
    if (endS > durationS) return setError(`The lecture ends at ${formatTimestamp(durationS)}.`)
    if (startS < prevEndS || endS > nextStartS) return setError('Clips can’t overlap their neighbours.')
    const failed = await onEdit({ title, startS, endS })
    setError(failed)
    if (!failed) setEditing(false)
  }

  return (
    <li id={`review-${clip.id}`} className={cn('scroll-mt-24 px-5 py-4', clip.status === 'rejected' && 'opacity-60')}>
      {editing ? (
        <form onSubmit={(e) => void save(e)} className="space-y-3">
          <input name="title" defaultValue={clip.title} aria-label="Clip title" className={cn(field, 'w-full font-medium')} />
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <input name="start" defaultValue={formatTimestamp(clip.startS)} aria-label="Start time" className={cn(field, 'w-24 tabular-nums')} />
            <span aria-hidden>–</span>
            <input name="end" defaultValue={formatTimestamp(clip.endS)} aria-label="End time" className={cn(field, 'w-24 tabular-nums')} />
            <Button type="submit" size="sm">Save</Button>
            <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setError(null) }}>Cancel</Button>
          </div>
          {error && <p className="text-sm text-bad" role="alert">{error}</p>}
        </form>
      ) : (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <Badge tone={meta.tone}>
                <span aria-hidden>{meta.icon}</span>&nbsp;{meta.label}
              </Badge>
              <span className="tabular-nums">
                {formatTimestamp(clip.startS)}–{formatTimestamp(clip.endS)}
              </span>
              <Badge tone="accent">{clip.topic}</Badge>
              {edited && <span>edited</span>}
            </div>
            <p className="mt-1 font-medium">{clip.title}</p>
            <p className="mt-0.5 text-sm text-muted">{clip.summary}</p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-1.5">
            <Button variant="ghost" size="sm" onClick={onPreview}>▶ Preview</Button>
            <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>Edit</Button>
            {clip.status !== 'approved' && (
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => onStatus('approved')}>Approve</Button>
            )}
            {clip.status !== 'rejected' && (
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => onStatus('rejected')}>Reject</Button>
            )}
            {clip.decided && (
              <Button variant="ghost" size="sm" disabled={busy} onClick={onReset} title="Undo your decision and edits">Undo</Button>
            )}
          </div>
        </div>
      )}
    </li>
  )
}
