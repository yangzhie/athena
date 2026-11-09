import { cn } from '../../lib/cn'

export interface MasteryBarProps {
  /** Mastery estimate from 0 to 1. */
  value: number
  label?: string
  className?: string
}

function tone(value: number) {
  if (value >= 0.8) return 'bg-good'
  if (value >= 0.4) return 'bg-warn'
  return 'bg-bad'
}

export function MasteryBar({ value, label, className }: MasteryBarProps) {
  const v = Math.min(1, Math.max(0, value))
  const pct = Math.round(v * 100)
  return (
    <div className={className}>
      {label && (
        <div className="mb-1 flex justify-between text-sm">
          <span>{label}</span>
          <span className="text-muted tabular-nums">{pct}%</span>
        </div>
      )}
      <div
        className="h-2 overflow-hidden rounded-full bg-line"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label={label ?? 'Mastery'}
      >
        <div className={cn('h-full rounded-full transition-all', tone(v))} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
