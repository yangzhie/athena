import { cn } from '../../core/cn'
import type { SortBenchState } from '../sortBench/module'
import type { ObjectViewProps } from '../types'
import { traceOf } from './module'

/** The source with the line the bench's trace reached highlighted, and the variables at that point. */
export function SortCodeView({ object, peers }: ObjectViewProps<'sort-code', null>) {
  const bench = peers.find((p) => p.type === 'sort-bench')?.state as SortBenchState | undefined
  const trace = bench ? traceOf(bench) : null
  const current = trace?.line ? object.config.lines[trace.line] : null

  return (
    <div className="space-y-2 p-3">
      <pre className="overflow-x-auto rounded-lg bg-bg py-2 font-mono text-xs leading-5">
        {object.config.source.split('\n').map((text, k) => (
          <div
            key={k}
            className={cn('flex px-2 transition-colors', k + 1 === current && 'bg-accent-soft font-semibold text-accent')}
          >
            <span className="w-6 shrink-0 select-none pr-2 text-right text-muted/60">{k + 1}</span>
            <span className="whitespace-pre">{text || ' '}</span>
          </div>
        ))}
      </pre>
      {trace ? (
        <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-xs">
          {Object.entries(trace.vars).map(([name, value]) => (
            <span key={name}>
              <span className="text-muted">{name} =</span> {value}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted">Give it the same experimentId as a sort bench to follow its trace.</p>
      )}
    </div>
  )
}
