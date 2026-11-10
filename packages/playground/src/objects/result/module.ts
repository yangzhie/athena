import type { ResultConfig } from '../../contracts'
import { defineModule } from '../types'
import { ResultView } from './ResultView'
import { s } from '../../core/schema'

export const resultModule = defineModule<'result', null>({
  type: 'result',
  label: 'Result',
  about: {
    summary:
      'A small table of results. Either fixed rows, or `compareRuns` to show the last two runs of the code graph in the same experiment (give both the same experimentId) side by side.',
    config: s.object(
      {
        rows: s.array(s.object({ label: s.string(), value: s.string(), note: s.string() }, ['label', 'value'])),
        compareRuns: s.object({ value: s.string('Top-level name to compare, e.g. "average"'), also: s.string('Another name shown as a note') }, ['value']),
        caption: s.string(),
      },
      [],
    ),
  },
  width: 320,
  init: () => null,
  reduce: (state) => state,
  summarize: (_state, config: ResultConfig) => (config.compareRuns ? { comparesRunsOf: config.compareRuns.value } : { rows: config.rows }),
  View: ResultView,
})
