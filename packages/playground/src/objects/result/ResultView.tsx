import type { ResultConfig } from '../../contracts'
import { deriveGraph } from '../codeGraph/graph'
import type { CodeGraphState } from '../codeGraph/module'
import type { CanvasObject, ObjectViewProps } from '../types'

type Row = NonNullable<ResultConfig['rows']>[number]

/** The filter condition a run used, as a readable label for that run. */
function conditionOf(source: string) {
  try {
    return deriveGraph(source).nodes.find((n) => n.filter)?.filter?.condition ?? 'run'
  } catch {
    return 'run'
  }
}

/** Rows comparing the last two runs of the code graph in the same experiment. */
function runRows(peers: CanvasObject[], compare: NonNullable<ResultConfig['compareRuns']>): Row[] {
  const code = peers.find((p) => p.type === 'code-graph')?.state as CodeGraphState | undefined
  const runs = [code?.previousRun, code?.lastRun].filter((r) => r != null)
  return runs.map((r) => ({
    label: `if ${conditionOf(r.source)}`,
    value: r.values[compare.value] ?? (r.error ? r.error.type : '—'),
    note: compare.also && r.values[compare.also] ? `${compare.also} ${r.values[compare.also]}` : undefined,
  }))
}

export function ResultView({ object, peers }: ObjectViewProps<'result', null>) {
  const { rows = [], compareRuns, caption } = object.config
  const shown = compareRuns ? runRows(peers, compareRuns) : rows
  return (
    <div className="p-3">
      <table className="w-full text-sm">
        <tbody>
          {shown.map((r, i) => (
            <tr key={i} className="border-b border-line last:border-0">
              <td className="py-1.5 pr-3 font-mono text-xs text-muted">{r.label}</td>
              <td className="py-1.5 font-mono font-semibold">{r.value}</td>
              {r.note && <td className="py-1.5 pl-2 text-xs text-muted">{r.note}</td>}
            </tr>
          ))}
          {!shown.length && (
            <tr>
              <td className="py-1.5 text-xs text-muted">Waiting for a run…</td>
            </tr>
          )}
        </tbody>
      </table>
      {caption && <p className="mt-2 text-xs text-muted">{caption}</p>}
    </div>
  )
}
