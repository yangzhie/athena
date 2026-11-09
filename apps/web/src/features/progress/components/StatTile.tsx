import { masteryMeta, type MasteryLevel } from '../../../lib/mastery'

export function StatTile({ level, value, total }: { level: MasteryLevel; value: number; total: number }) {
  const meta = masteryMeta[level]
  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <p className="flex items-center gap-1.5 text-sm text-muted">
        <span aria-hidden className={meta.text}>
          {meta.icon}
        </span>
        {meta.label}
      </p>
      <p className="mt-1 text-3xl font-semibold tabular-nums">
        {value}
        <span className="ml-1 text-base font-normal text-muted">/ {total}</span>
      </p>
    </div>
  )
}
