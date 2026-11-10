import type { Actor, Observation, PotentialLogConfig } from '../../contracts'
import type { MeterReading } from '../halfCell/electrochem'
import { defineModule, type Wiring } from '../types'
import { PotentialLogView } from './PotentialLogView'
import { s } from '../../core/schema'

export interface LogRow {
  n: number
  red: string | null // e.g. "Cu, 1.00 M"
  black: string | null
  volts: number
  by: Actor
}

export interface PotentialLogState {
  rows: LogRow[]
  /** What the meter showed at the last recording, kept for checks. */
  last: MeterReading | null
}

/** What the connected instrument shows right now, if one is plugged in. */
export function connectedReading(w: Wiring): MeterReading | null {
  const ref = w.peers('in')[0]
  return ref ? ((w.read(ref) as MeterReading | undefined) ?? null) : null
}

const side = (e: MeterReading['red']) => (e ? `${e.metal}, ${e.concentration.toFixed(e.concentration >= 0.1 ? 2 : 3)} M` : null)

export const potentialLogModule = defineModule<'potential-log', PotentialLogState>({
  type: 'potential-log',
  label: 'Lab notebook',
  about: {
    summary: "A lab notebook that records the reading of the meter whose data cable is plugged into its `in` socket. Pre-plug the cable with the scene's `wiring`.",
    config: s.empty(),
    actions: { recordReading: '{}: record what the meter shows' },
    observes: {
      on: ['recordReading'],
      fields: {
        connected: 'a meter is plugged in',
        circuit: '"unplugged" (a lead hangs free), "same-cell", "open" (no salt bridge between the two cells) or "closed"',
        volts: 'the reading, V',
        red: 'metal under the red lead, or null',
        black: 'metal under the black lead, or null',
        pair: 'the two metals, sorted and joined with "|", e.g. "Cu|Zn"',
        standard: 'both solutions are at 1.00 M',
      },
    },
  },
  width: 440,
  ports: {
    in: { kind: 'data', role: 'socket', at: { x: 0, y: 19 } },
  },
  init: (): PotentialLogState => ({ rows: [], last: null }),
  edits: ['recordReading'],
  reduce(state, action, _config: PotentialLogConfig, actor, wiring) {
    if (action.type !== 'recordReading') return state
    const m = connectedReading(wiring)
    if (!m) return { ...state, last: null }
    // With a lead hanging free there is nothing worth writing down; the check still explains why.
    if (m.circuit === 'unplugged') return { ...state, last: m }
    const row: LogRow = { n: state.rows.length + 1, red: side(m.red), black: side(m.black), volts: Number(m.volts.toFixed(3)), by: actor }
    return { rows: [...state.rows, row], last: m }
  },
  observe(state, action): Observation | null {
    if (action.type !== 'recordReading') return null
    const m = state.last
    if (!m) return { action: 'recordReading', connected: false }
    const metals = [m.red?.metal, m.black?.metal].filter(Boolean).sort()
    return {
      action: 'recordReading',
      connected: true,
      circuit: m.circuit,
      volts: Number(m.volts.toFixed(3)),
      red: m.red?.metal ?? null,
      black: m.black?.metal ?? null,
      pair: metals.join('|'),
      standard: [m.red, m.black].every((e) => e && Math.abs(e.concentration - 1) < 1e-9),
    }
  },
  anchor: () => 'record',
  summarize(state, _config, wiring) {
    return { instrumentConnected: Boolean(wiring.peers('in').length), rows: state.rows }
  },
  View: PotentialLogView,
})
