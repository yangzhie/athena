import type { SaltBridgeConfig } from '../../contracts'
import type { BridgeEnd } from '../halfCell/electrochem'
import { defineModule, type Wiring } from '../types'
import { SaltBridgeView } from './SaltBridgeView'
import { s } from '../../core/schema'

export const SALT_BRIDGE = { w: 150, h: 64 }

/** The beaker an end of the bridge dips into. */
const beakerAt = (w: Wiring, end: 'a' | 'b') => {
  const ref = w.peers(end)[0]
  return ref ? ((w.read(ref) as { cell?: string } | undefined)?.cell ?? null) : null
}

export const saltBridgeModule = defineModule<'salt-bridge', null>({
  type: 'salt-bridge',
  label: 'Salt bridge',
  about: {
    summary: 'A salt bridge with two tube ends (plugs `a` and `b`, kind bridge). Dipping one end into each half-cell `solution` lets ions flow and closes the circuit.',
    config: s.object({ electrolyte: s.string('e.g. "KNO₃"') }),
    actions: { connect: '{plug: "a" | "b", to: {objectId, port: "solution"} | null}' },
    observes: { on: ['connect'], fields: { sameBeaker: 'both ends are in the same beaker' } },
  },
  width: SALT_BRIDGE.w,
  size: SALT_BRIDGE,
  ports: {
    a: { kind: 'bridge', role: 'plug', at: { x: 14, y: 34 }, rest: { x: 0, y: 110 }, look: 'tube' },
    b: { kind: 'bridge', role: 'plug', at: { x: 136, y: 34 }, rest: { x: 150, y: 110 }, look: 'tube' },
  },
  init: () => null,
  edits: ['connect'],
  reduce: (state) => state,
  read(_state, _config: SaltBridgeConfig, port, wiring): BridgeEnd {
    return { otherCell: beakerAt(wiring, port === 'a' ? 'b' : 'a') }
  },
  observe(_state, action, _config, wiring) {
    if (action.type !== 'connect') return null
    const a = beakerAt(wiring, 'a')
    const b = beakerAt(wiring, 'b')
    if (!a || !b) return null
    return { action: 'connect', sameBeaker: a === b }
  },
  summarize(_state, config, wiring) {
    return { electrolyte: config.electrolyte, endA: beakerAt(wiring, 'a'), endB: beakerAt(wiring, 'b') }
  },
  View: SaltBridgeView,
})
