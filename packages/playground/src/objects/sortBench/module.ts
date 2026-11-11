import type { Observation, SortBenchConfig } from '../../contracts'
import { defineModule } from '../types'
import { SortBenchView } from './SortBenchView'
import { s } from '../../core/schema'

/** A value with a stable identity, so equal values can be told apart (and animated). */
export interface SortItem {
  id: number
  value: number
}

export interface PassRecord {
  pass: number
  values: number[]
  comparisons: number
  swaps: number
}

export interface SortBenchState {
  items: SortItem[]
  /** The pass in progress, from 1. */
  pass: number
  /** Left index of the pair the pass has reached. */
  cursor: number
  /** Items from this index on are in their final place. */
  sortedFrom: number
  passComparisons: number
  passSwaps: number
  comparisons: number
  swaps: number
  history: PassRecord[]
  /** The last decision, kept for checks and for highlighting its pair. */
  last: { action: 'swap' | 'keep'; index: number; left: SortItem; right: SortItem; pass: number; passEnded: boolean; passSwaps: number } | null
  /** The student said the algorithm can stop, and it can. */
  finished: boolean
}

const values = (items: SortItem[]) => items.map((i) => i.value)

export const isSorted = (items: SortItem[]) => items.every((it, i) => i === 0 || items[i - 1].value <= it.value)

/** The algorithm itself only knows it's done after a pass without swaps, or once every pass has run. */
export const canStop = (s: SortBenchState) => s.history.at(-1)?.swaps === 0 || s.sortedFrom <= 1

function init(config: SortBenchConfig): SortBenchState {
  return {
    items: config.values.map((value, id) => ({ id, value })),
    pass: 1,
    cursor: 0,
    sortedFrom: config.values.length,
    passComparisons: 0,
    passSwaps: 0,
    comparisons: 0,
    swaps: 0,
    history: [],
    last: null,
    finished: false,
  }
}

export const sortBenchModule = defineModule<'sort-bench', SortBenchState>({
  type: 'sort-bench',
  label: 'Sort bench',
  about: {
    summary:
      'A row of values drawn as bars that the student sorts by hand with bubble sort: in the highlighted pair they drag one bar past the other to swap them, or drag the arrow under the pair on (or tap it) to keep them. A pass ends by itself at the values already in their final place (shown in green). Done says the algorithm can stop. The table lists each pass with its comparisons and swaps.',
    config: s.object({
      algorithm: s.string('The algorithm being traced', ['bubble']),
      values: s.array(s.integer('A value', 1, 99), 'The starting order; repeat a value to discuss stability', 2, 10),
    }),
    actions: {
      swap: '{index}: swap the pair at index and index + 1 (must be the pair the pass has reached)',
      keep: '{index}: leave that pair as it is',
      finish: '{}: say the algorithm can stop now',
      resetSort: '{}: back to the starting order (throws the attempt away; the student is asked first)',
    },
    observes: {
      on: ['swap', 'keep', 'finish'],
      fields: {
        index: 'swap/keep: left index of the pair',
        left: 'swap/keep: left value before the decision',
        right: 'swap/keep: right value before the decision',
        outOfOrder: 'swap/keep: left > right, so bubble sort swaps',
        equal: 'swap/keep: the two values are equal (swapping them breaks stability)',
        pass: 'swap/keep: the pass the decision belongs to',
        passEnded: 'swap/keep: this decision finished the pass',
        passSwaps: 'swap/keep: swaps so far in that pass',
        sorted: 'finish: the values are in order',
        verified: 'finish: the algorithm can know it is done (the last pass made no swaps, or every pass has run)',
        passes: 'finish: passes completed',
        comparisons: 'finish: comparisons made so far',
      },
    },
  },
  width: 560,
  init,
  edits: ['swap', 'keep', 'finish', 'resetSort'],
  resets: ['resetSort'],
  reduce(state, action, config) {
    switch (action.type) {
      case 'swap':
      case 'keep': {
        if (state.finished || state.sortedFrom <= 1 || action.index !== state.cursor) return state
        const i = action.index
        const [left, right] = [state.items[i], state.items[i + 1]]
        const items = action.type === 'swap' ? state.items.map((it, k) => (k === i ? right : k === i + 1 ? left : it)) : state.items
        const passSwaps = state.passSwaps + (action.type === 'swap' ? 1 : 0)
        const passComparisons = state.passComparisons + 1
        const passEnded = i + 1 >= state.sortedFrom - 1
        const next = {
          ...state,
          items,
          comparisons: state.comparisons + 1,
          swaps: state.swaps + (action.type === 'swap' ? 1 : 0),
          last: { action: action.type, index: i, left, right, pass: state.pass, passEnded, passSwaps },
        }
        if (!passEnded) return { ...next, cursor: i + 1, passComparisons, passSwaps }
        // The largest value left has bubbled into place; the next pass stops one pair earlier.
        const record: PassRecord = { pass: state.pass, values: values(items), comparisons: passComparisons, swaps: passSwaps }
        return { ...next, history: [...state.history, record], pass: state.pass + 1, cursor: 0, sortedFrom: state.sortedFrom - 1, passComparisons: 0, passSwaps: 0 }
      }
      case 'finish':
        return { ...state, finished: isSorted(state.items) && canStop(state) }
      case 'resetSort':
        return init(config)
    }
    return state
  },
  observe(state, action): Observation | null {
    switch (action.type) {
      case 'swap':
      case 'keep': {
        const l = state.last
        if (!l) return null
        return {
          action: action.type,
          index: l.index,
          left: l.left.value,
          right: l.right.value,
          outOfOrder: l.left.value > l.right.value,
          equal: l.left.value === l.right.value,
          pass: l.pass,
          passEnded: l.passEnded,
          passSwaps: l.passSwaps,
        }
      }
      case 'finish':
        return {
          action: 'finish',
          sorted: isSorted(state.items),
          verified: canStop(state),
          passes: state.history.length,
          comparisons: state.comparisons,
        }
    }
    return null
  },
  validate(state, action) {
    if ((action.type === 'swap' || action.type === 'keep') && action.index !== state.cursor) {
      return `the pass has reached the pair at ${state.cursor} and ${state.cursor + 1}`
    }
    return null
  },
  anchor(action) {
    if (action.type === 'swap') return 'pair'
    if (action.type === 'keep') return 'next'
    if (action.type === 'finish') return 'finish'
    if (action.type === 'resetSort') return 'reset'
    return 'bars'
  },
  summarize(state, config) {
    return {
      algorithm: config.algorithm,
      values: values(state.items),
      pass: state.pass,
      comparingPositions: state.finished || state.sortedFrom <= 1 ? null : [state.cursor, state.cursor + 1],
      finalFrom: state.sortedFrom,
      comparisons: state.comparisons,
      swaps: state.swaps,
      passes: state.history,
      finished: state.finished,
    }
  },
  View: SortBenchView,
})
