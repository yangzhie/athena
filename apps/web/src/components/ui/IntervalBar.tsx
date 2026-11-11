import { cn } from '../../lib/cn'

export interface IntervalBarProps {
  /** Point estimate from 0 to 1. */
  value: number
  /** 95% interval bounds from 0 to 1. */
  low: number
  high: number
  /** What the estimate measures, e.g. "Answered correctly". */
  label: string
  /** Bar colour class for the estimate, e.g. "bg-accent". */
  tone?: string
  className?: string
}

const pct = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 100)

/** An estimate with its 95% interval shaded behind it. */
export function IntervalBar({ value, low, high, label, tone = 'bg-accent', className }: IntervalBarProps) {
  const [v, l, h] = [pct(value), pct(low), pct(high)]
  const text = `${label}: ${v}%, 95% interval ${l} to ${h}%`
  return (
    <div className={className}>
      <div className="mb-1 flex justify-between gap-3 text-sm">
        <span className="text-muted">{label}</span>
        <span className="shrink-0 tabular-nums">
          {v}% <span className="text-muted">(95% CI {l}–{h}%)</span>
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-line" role="img" aria-label={text}>
        <div className={cn('absolute inset-y-0 rounded-full opacity-30', tone)} style={{ left: `${l}%`, width: `${Math.max(h - l, 1)}%` }} />
        <div className={cn('absolute inset-y-0 left-0 rounded-full', tone)} style={{ width: `${v}%` }} />
        <div className={cn('absolute -inset-y-1 w-0.5 rounded-full', tone)} style={{ left: `calc(${v}% - 1px)` }} aria-hidden />
      </div>
    </div>
  )
}
