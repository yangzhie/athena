import type { VoltmeterConfig } from '../../contracts'
import { measure } from '../halfCell/electrochem'
import { defineModule } from '../types'
import { VoltmeterView } from './VoltmeterView'
import { s } from '../../core/schema'

export const VOLTMETER = { w: 230, h: 150 }

export const voltmeterModule = defineModule<'voltmeter', null>({
  type: 'voltmeter',
  label: 'Voltmeter',
  about: {
    summary:
      'A digital voltmeter with a red lead `v` and a black lead `com` (kind lead) and a `data` cable (kind data). It shows E(red) − E(black) only when both leads are on electrodes of different half-cells joined by a salt bridge; otherwise 0.000 V, like a real meter.',
    config: s.empty(),
    actions: {
      connect: '{plug: "v" | "com" | "data", to: {objectId, port} | null}: clip a lead onto a half-cell `electrode`, or the cable into a log `in`',
      swapPlugs: '{plugs: ["v", "com"]}: swap the two leads',
    },
  },
  width: VOLTMETER.w,
  size: VOLTMETER,
  ports: {
    v: { kind: 'lead', role: 'plug', at: { x: 150, y: 138 }, rest: { x: 166, y: 210 }, look: 'red', label: 'V (red)' },
    com: { kind: 'lead', role: 'plug', at: { x: 80, y: 138 }, rest: { x: 64, y: 210 }, look: 'black', label: 'COM' },
    data: { kind: 'data', role: 'plug', at: { x: 230, y: 50 }, rest: { x: 280, y: 80 }, look: 'data', label: 'data' },
  },
  init: () => null,
  edits: ['connect'],
  reduce: (state) => state,
  read: (_state, _config: VoltmeterConfig, port, wiring) => (port === 'data' ? measure(wiring) : undefined),
  summarize(_state, _config, wiring) {
    const m = measure(wiring)
    return {
      display_V: Number(m.volts.toFixed(3)),
      redLeadOn: m.red ? `${m.red.metal} electrode (${m.red.cell})` : null,
      comLeadOn: m.black ? `${m.black.metal} electrode (${m.black.cell})` : null,
      circuit: m.circuit,
    }
  },
  View: VoltmeterView,
})
