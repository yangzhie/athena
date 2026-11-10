import type { HalfCellConfig } from '../../contracts'
import { defineModule } from '../types'
import { electrodePotential, type BridgeEnd, type Electrode } from './electrochem'
import { HalfCellView } from './HalfCellView'
import { s } from '../../core/schema'

export interface HalfCellState {
  concentration: number
}

export const HALF_CELL = { w: 200, h: 312 }

export const halfCellModule = defineModule<'half-cell', HalfCellState>({
  type: 'half-cell',
  label: 'Half-cell',
  about: {
    summary:
      'A beaker half-cell: a metal electrode in a solution of its ions, drawn as apparatus. Sockets: `electrode` (for meter leads) and `solution` (for salt-bridge ends). The student can dilute the solution tenfold or refill it. Its potential follows the Nernst equation at 25 °C.',
    config: s.object({
      metal: s.string('Element symbol, e.g. "Zn"'),
      ion: s.string('e.g. "Zn²⁺"'),
      electrons: s.integer('n in M^n+ + n e⁻ → M', 1, 4),
      standardPotential: s.number('E° vs SHE in volts', -3.1, 3),
      concentration: s.number('mol/L at the start', 0.0001, 6),
      solutionColor: s.string('CSS colour of the solution, e.g. "#2563eb" for Cu²⁺'),
    }),
    actions: { dilute: '{}: dilute tenfold', refill: '{}: back to the starting concentration' },
  },
  width: HALF_CELL.w,
  size: HALF_CELL,
  ports: {
    electrode: { kind: 'lead', role: 'socket', at: { x: 62, y: 30 } },
    solution: { kind: 'bridge', role: 'socket', at: { x: 124, y: 142 } },
  },
  init: (config: HalfCellConfig) => ({ concentration: config.concentration }),
  edits: ['dilute', 'refill'],
  reduce(state, action, config) {
    if (action.type === 'dilute') return { concentration: Math.max(1e-4, state.concentration / 10) }
    if (action.type === 'refill') return { concentration: config.concentration }
    return state
  },
  read(state, config, port, wiring) {
    if (port === 'solution') return { cell: wiring.self }
    if (port !== 'electrode') return undefined
    const bridgedTo = wiring
      .peers('solution')
      .map((ref) => (wiring.read(ref) as BridgeEnd | undefined)?.otherCell)
      .filter((c): c is string => Boolean(c) && c !== wiring.self)
    return {
      cell: wiring.self,
      metal: config.metal,
      ion: config.ion,
      concentration: state.concentration,
      potential: electrodePotential(config, state.concentration),
      bridgedTo,
    } satisfies Electrode
  },
  anchor: (action) => (action.type === 'dilute' || action.type === 'refill' ? action.type : 'beaker'),
  summarize(state, config, wiring) {
    return {
      halfCell: `${config.metal} | ${config.ion}`,
      concentration_M: state.concentration,
      leadsAttached: wiring.peers('electrode').length,
      saltBridgeEnds: wiring.peers('solution').length,
    }
  },
  View: HalfCellView,
})
