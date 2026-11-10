import { cn } from '../../../lib/cn'
import { formatTimestamp } from '../../../lib/format'
import type { ReviewedClip } from './types'

const fill = { approved: 'bg-good', rejected: 'bg-line', pending: 'bg-warn' } as const

/** The whole lecture as a bar, with each proposed clip as a block. Click a block to jump to its row. */
export function ReviewTimeline({ clips, durationS }: { clips: ReviewedClip[]; durationS: number }) {
  return (
    <div>
      <div className="relative h-6 overflow-hidden rounded-md bg-line/40">
        {clips.map((c) => (
          <a
            key={c.id}
            href={`#review-${c.id}`}
            title={`${formatTimestamp(c.startS)}–${formatTimestamp(c.endS)} · ${c.title} (${c.status})`}
            aria-label={`${c.title}, ${c.status}`}
            className={cn('absolute inset-y-0 border-x border-surface transition-opacity hover:opacity-80', fill[c.status])}
            style={{ left: `${(c.startS / durationS) * 100}%`, width: `${((c.endS - c.startS) / durationS) * 100}%` }}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-xs text-muted tabular-nums">
        <span>00:00</span>
        <span>{formatTimestamp(durationS)}</span>
      </div>
    </div>
  )
}
