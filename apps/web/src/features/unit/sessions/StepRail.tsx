import { cn } from '../../../lib/cn'
import { STAGES, type LessonProgress } from '../chat/lessonProgress'

/** Diagnose → Teach → Check → Done, with the current stage highlighted and a running tally. */
export function StepRail({ progress }: { progress: LessonProgress }) {
  const current = STAGES.findIndex((s) => s.id === progress.stage)
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
      <ol className="flex items-center" aria-label="Lesson stages">
        {STAGES.map((s, i) => {
          const done = i < current || progress.stage === 'done'
          const now = i === current && progress.stage !== 'done'
          return (
            <li key={s.id} className="flex items-center" aria-current={now ? 'step' : undefined}>
              {i > 0 && <span aria-hidden className={cn('mx-1.5 h-px w-4 sm:mx-2 sm:w-10', i <= current ? 'bg-accent' : 'bg-line')} />}
              <span className="flex items-center gap-1.5">
                <span
                  aria-hidden
                  className={cn(
                    'grid size-5 place-items-center rounded-full border-2 text-[0.65rem] font-bold',
                    done && 'border-accent bg-accent text-surface',
                    now && 'border-accent bg-surface',
                    !done && !now && 'border-line',
                  )}
                >
                  {done ? '✓' : now ? <span className="size-2 rounded-full bg-accent" /> : null}
                </span>
                {/* Phones: only the current stage is named, so the rail fits. */}
                <span className={cn('text-sm', now ? 'font-semibold text-ink highlight' : cn('sr-only sm:not-sr-only', done ? 'text-ink' : 'text-muted'))}>
                  {s.label}
                </span>
              </span>
            </li>
          )
        })}
      </ol>
      {progress.answered > 0 && (
        <p className="text-sm text-muted tabular-nums">
          {progress.answered} answered · <span className="text-good">{progress.correct} correct</span>
        </p>
      )}
    </div>
  )
}
