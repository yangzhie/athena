import { cn } from '../../lib/cn'
import { masteryLevel, masteryMeta } from '../../lib/mastery'

export interface MasteryBarProps {
  /** Mastery estimate from 0 to 1. */
  value: number
  label?: string
  className?: string
}

export function MasteryBar({ value, label, className }: MasteryBarProps) {
  const v = Math.min(1, Math.max(0, value))
  const pct = Math.round(v * 100)
  const meta = masteryMeta[masteryLevel(v)]
  return (
    <div className={className}>
      {label && (
        <div className="mb-1 flex justify-between gap-3 text-sm">
          <span className="truncate">{label}</span>
          <span className="shrink-0 text-muted tabular-nums">
            <span aria-hidden>{meta.icon}</span> {meta.label} · {pct}%
          </span>
        </div>
      )}
      <div
        className="h-2 overflow-hidden rounded-full bg-line"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={`${pct}%, ${meta.label}`}
        aria-label={label ?? 'Mastery'}
      >
        <div className={cn('h-full rounded-full transition-all', meta.bar)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
