import type { PhotogateConfig } from '../../contracts'
import type { SwingReading } from '../pendulum/physics'
import { defineModule, type Wiring } from '../types'
import { PhotogateView } from './PhotogateView'
import { s } from '../../core/schema'

/** What the photogate's sensor sees: the pendulum it is clipped onto, if any. */
export function gateReading(w: Wiring): SwingReading | null {
  const ref = w.peers('gate')[0]
  return ref ? ((w.read(ref) as SwingReading | undefined) ?? null) : null
}

export const photogateModule = defineModule<'photogate', null>({
  type: 'photogate',
  label: 'Photogate timer',
  about: {
    summary:
      "A photogate timer. Its `gate` plug (kind sensor) clips onto a pendulum's `gate` socket at the bottom of the swing, and it then shows the period to the millisecond. Its `data` cable carries the reading to a pendulum log `in` socket (pre-plug it with the scene `wiring`).",
    config: s.empty(),
    actions: { connect: '{plug: "gate" | "data", to: {objectId, port} | null}' },
  },
  width: 280,
  ports: {
    gate: { kind: 'sensor', role: 'plug', at: { x: 0, y: 19 }, rest: { x: -40, y: 70 }, look: 'black', label: 'photogate' },
    data: { kind: 'data', role: 'plug', at: { x: 280, y: 19 }, rest: { x: 320, y: 60 }, look: 'data', label: 'data' },
  },
  init: () => null,
  edits: ['connect'],
  reduce: (state) => state,
  read: (_state, _config: PhotogateConfig, port, wiring) => (port === 'data' ? gateReading(wiring) : undefined),
  summarize: (_state, _config, wiring) => {
    const r = gateReading(wiring)
    return r ? { clippedOn: wiring.peers('gate')[0].objectId, period_s: r.period } : { clippedOn: null }
  },
  View: PhotogateView,
})
