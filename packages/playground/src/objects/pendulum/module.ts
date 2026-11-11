import type { PendulumConfig } from '../../contracts'
import { defineModule } from '../types'
import { PendulumView } from './PendulumView'
import { periodOf, type SwingReading } from './physics'
import { s } from '../../core/schema'

export interface PendulumState {
  length: number
  mass: number
  amplitude: number
}

export const PENDULUM = { w: 260, h: 430 }
/** World pixels per metre of string. */
export const PX_PER_M = 180
/** Where the bob hangs at rest. The pivot moves with the length, so this point stays put. */
export const LOWEST = { x: 130, y: 330 }
/** Where the photogate clips on: straddling the bottom of the swing. */
export const GATE = { x: LOWEST.x, y: LOWEST.y + 32 }
export const LENGTHS: [number, number] = [0.2, 1.5]
export const MASSES = [50, 100, 200]
/** Release angles the student can pull the bob out to, degrees. */
export const AMPLITUDE_RANGE: [number, number] = [2, 60]

const round2 = (x: number) => Math.round(x * 100) / 100

export const pendulumModule = defineModule<'pendulum', PendulumState>({
  type: 'pendulum',
  label: 'Pendulum',
  about: {
    summary:
      'A simple pendulum on a stand, drawn as apparatus and always swinging. Everything is direct manipulation: the student pulls the bob sideways to set the release angle (2–60°), drags the pivot up or down to set the string length (0.20–1.50 m), and drags a 50, 100 or 200 g bob from the tray onto the string. Its `gate` socket (kind sensor) is the lowest point of the swing, where a photogate clips on. The period includes the large-amplitude correction, so readings above about 15° come out noticeably long.',
    config: s.object({ g: s.number('m/s², what the student is meant to find', 1, 30) }),
    actions: {
      setLength: '{metres}: string length, 0.20–1.50 m',
      setMass: '{grams}: 50, 100 or 200',
      setAmplitude: '{degrees}: release angle, 2–60',
    },
  },
  width: PENDULUM.w,
  size: PENDULUM,
  ports: {
    gate: { kind: 'sensor', role: 'socket', at: GATE, about: 'The lowest point of the swing, where a photogate clips on' },
  },
  init: () => ({ length: 1, mass: 100, amplitude: 10 }),
  edits: ['setLength', 'setMass', 'setAmplitude'],
  reduce(state, action) {
    switch (action.type) {
      case 'setLength':
        return { ...state, length: round2(Math.min(LENGTHS[1], Math.max(LENGTHS[0], action.metres))) }
      case 'setMass':
        return MASSES.includes(action.grams) ? { ...state, mass: action.grams } : state
      case 'setAmplitude':
        return { ...state, amplitude: Math.round(Math.min(AMPLITUDE_RANGE[1], Math.max(AMPLITUDE_RANGE[0], action.degrees))) }
    }
    return state
  },
  read(state, config: PendulumConfig, port): SwingReading | undefined {
    if (port !== 'gate') return undefined
    return { length: state.length, mass: state.mass, amplitude: state.amplitude, period: Number(periodOf(state.length, config.g, state.amplitude).toFixed(3)) }
  },
  // The hand drags the pivot and pulls the bob rather than jumping them.
  tween(state, action) {
    const frames = 30
    if (action.type === 'setLength')
      return Array.from({ length: frames }, (_, i) => ({ type: 'setLength' as const, metres: state.length + ((i + 1) / frames) * (action.metres - state.length) }))
    if (action.type === 'setAmplitude')
      return Array.from({ length: frames }, (_, i) => ({ type: 'setAmplitude' as const, degrees: state.amplitude + ((i + 1) / frames) * (action.degrees - state.amplitude) }))
    return []
  },
  anchor(action) {
    if (action.type === 'setMass') return `mass-${action.grams}`
    if (action.type === 'setAmplitude') return 'bob'
    return 'pivot'
  },
  summarize: (state) => ({ length_m: state.length, mass_g: state.mass, amplitude_deg: state.amplitude }),
  View: PendulumView,
})
