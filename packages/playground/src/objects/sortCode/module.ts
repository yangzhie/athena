import type { SortCodeConfig } from '../../contracts'
import type { SortBenchState } from '../sortBench/module'
import { defineModule } from '../types'
import { SortCodeView } from './SortCodeView'
import { s } from '../../core/schema'

export type TraceLine = keyof SortCodeConfig['lines']

/** Where the code is after the bench's last decision, and the variables at that point. */
export function traceOf(bench: SortBenchState) {
  const last = bench.last
  let line: TraceLine | null = null
  if (bench.finished) line = 'stop'
  else if (last?.passEnded) line = last.passSwaps === 0 ? 'stop' : 'passEnd'
  else if (last) line = last.action === 'swap' ? 'swap' : 'compare'
  return {
    line,
    vars: {
      n: String(bench.items.length),
      i: String(last ? last.pass - 1 : 0),
      j: last ? String(last.index) : '—',
      swapped: last && last.passSwaps > 0 ? 'True' : 'False',
      a: `[${bench.items.map((it) => it.value).join(', ')}]`,
    },
  }
}

const line = (description: string) => s.integer(description, 1, 60)

export const sortCodeModule = defineModule<'sort-code', null>({
  type: 'sort-code',
  label: 'Code',
  about: {
    summary:
      'The sorting code, shown next to the sort bench with the same experimentId. As the student decides pairs on the bench it highlights the line that ran (compare, swap, the end-of-pass check or break) and shows i, j, swapped and the list.',
    config: s.object({
      language: s.string('Always "python"', ['python']),
      source: s.string('The program'),
      lines: s.object({
        compare: line('Line of `if a[j] > a[j + 1]`'),
        swap: line('Line of the swap'),
        passEnd: line('Line of `if not swapped`'),
        stop: line('Line of `break`'),
      }),
    }),
  },
  width: 420,
  init: () => null,
  reduce: (state) => state,
  summarize: (_state, config: SortCodeConfig) => ({ shows: 'the code of the sort bench in the same experiment', lines: config.lines }),
  View: SortCodeView,
})
