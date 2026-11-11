import { cn } from '../../core/cn'
import type { ObjectViewProps } from '../types'
import type { PredictState } from './module'

export function PredictView({ object, state, dispatch, demonstrating }: ObjectViewProps<'predict', PredictState>) {
  return (
    <div className="space-y-2 p-3 text-sm">
      <p className="leading-relaxed">{object.config.question}</p>
      <div className="space-y-1.5">
        {object.config.options.map((option, i) => (
          <button
            key={i}
            type="button"
            data-anchor={`${object.id}/option-${i}`}
            disabled={demonstrating}
            onClick={() => dispatch({ type: 'choose', option: i })}
            className={cn(
              'flex w-full items-center gap-2 rounded-lg border px-3 py-1.5 text-left disabled:opacity-60',
              state.choice === i ? 'border-accent bg-accent-soft text-accent' : 'border-line hover:bg-line/50',
            )}
          >
            <span className={cn('h-3 w-3 shrink-0 rounded-full border', state.choice === i ? 'border-accent bg-accent' : 'border-muted')} />
            {option}
          </button>
        ))}
      </div>
    </div>
  )
}
