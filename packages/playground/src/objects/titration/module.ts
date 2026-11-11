import type { Rect, TitrationConfig } from '../../contracts'
import { defineModule } from '../types'
import { colourLevel, colourName, equivalenceVolume, pHAfter } from './chemistry'
import { TitrationView } from './TitrationView'
import { s } from '../../core/schema'

/** Size of the rig on the canvas, in world pixels. */
export const RIG = { w: 360, h: 760 }

/** Below this tap opening the burette drips; above it, it runs as a stream. */
export const DROPWISE_MAX = 0.35

export interface Trial {
  trial: number
  reading: number // mL
  by: 'student' | 'agent'
}

export interface TitrationState {
  origin: { x: number; y: number }
  opening: number
  /** Titrant dispensed this trial (mL); the burette reading. */
  volume: number
  /** Part of `volume` that hasn't been mixed in yet (a local flash where it landed). */
  unmixed: number
  /** Drops released so far, for the drop animation. */
  drops: number
  dropClock: number
  wobble: number
  trial: number
  trials: Trial[]
  /** Mixed-solution samples taken when the student swirls, for the titration curve. */
  samples: { volume: number; pH: number }[]
}

const round2 = (x: number) => Math.round(x * 100) / 100

export function flowOf(opening: number): 'closed' | 'dropwise' | 'stream' {
  return opening <= 0.02 ? 'closed' : opening <= DROPWISE_MAX ? 'dropwise' : 'stream'
}

/** Mixed-solution pH, ignoring titrant that hasn't been swirled in. */
export const bulkPH = (config: TitrationConfig, s: TitrationState) => pHAfter(config, s.volume - s.unmixed)

function dispense(s: TitrationState, config: TitrationConfig, ml: number): TitrationState {
  const add = Math.max(0, Math.min(ml, config.burette.capacity - s.volume))
  return { ...s, volume: s.volume + add, unmixed: s.unmixed + add }
}

function sample(s: TitrationState, config: TitrationConfig): TitrationState {
  const v = s.volume - s.unmixed
  if (s.samples.some((p) => Math.abs(p.volume - v) < 0.02)) return s
  return { ...s, samples: [...s.samples, { volume: v, pH: pHAfter(config, v) }].sort((a, b) => a.volume - b.volume) }
}

export const titrationModule = defineModule<'titration', TitrationState>({
  type: 'titration',
  label: 'Titration rig',
  about: {
    summary:
      'An acid–base titration rig: a burette of titrant over a flask of analyte with an indicator. The student turns the tap, swirls the flask by shaking it, records the endpoint and starts new trials. Ideal strong acid / strong base model.',
    config: s.object({
      analyte: s.object({ formula: s.string(), concentration: s.number('mol/L', 0.001, 2), volume: s.number('mL in the flask', 5, 100) }),
      titrant: s.object({ formula: s.string(), concentration: s.number('mol/L, hidden from the student', 0.001, 2), label: s.string() }),
      indicator: s.object({ name: s.string(), transition: s.array(s.number(), '[low, high] pH of the colour change', 2, 2) }),
      burette: s.object({ capacity: s.number('mL', 10, 100), dropVolume: s.number('mL', 0.01, 0.2) }),
    }),
    actions: {
      setTap: '{opening}: tap opening from 0 (closed) to 1 (fully open)',
      newTrial: '{}: refill the flask (throws the current attempt away; the student is asked first)',
      dispenseTo: '{volume, mode: "stream" | "dropwise"}: run titrant in to this burette reading',
      swirl: '{}: mix the flask',
      recordEndpoint: '{}: record the burette reading',
    },
    observes: {
      on: ['setTap', 'swirl', 'dispenseTo', 'recordEndpoint'],
      fields: {
        volume: 'mL dispensed',
        mixed: 'false while unmixed titrant is still in the flask',
        colour: '"colourless", "faint pink" or "deep pink"',
        toEquivalence: 'mL left to the equivalence point',
        flow: 'setTap: "closed", "dropwise" or "stream"',
        nearEndpoint: 'setTap: within ~2 mL of equivalence',
        reading: 'recordEndpoint: recorded reading in mL',
        overshoot: 'recordEndpoint: reading minus the equivalence volume',
      },
    },
  },
  width: RIG.w,
  init: () => ({
    origin: { x: 0, y: 0 },
    opening: 0,
    volume: 0,
    unmixed: 0,
    drops: 0,
    dropClock: 0,
    wobble: 0,
    trial: 1,
    trials: [],
    samples: [],
  }),
  bounds: (s) => ({ x: s.origin.x, y: s.origin.y, ...RIG }) satisfies Rect,
  placeAt: (s, x, y) => ({ ...s, origin: { x, y } }),
  edits: ['setTap', 'dispenseTo', 'swirl', 'recordEndpoint', 'newTrial'],
  resets: ['newTrial'],
  reduce(s, action, config, actor) {
    switch (action.type) {
      case 'setTap':
        return { ...s, opening: Math.min(1, Math.max(0, action.opening)), dropClock: 0 }
      case 'tick': {
        const flow = flowOf(s.opening)
        if (flow === 'closed' || s.volume >= config.burette.capacity) return s
        if (flow === 'stream') {
          const rate = 0.3 + ((s.opening - DROPWISE_MAX) / (1 - DROPWISE_MAX)) * 1.7 // mL/s
          return dispense(s, config, rate * action.dt)
        }
        // Dropwise: one drop every 1.2 s when barely open, every 0.25 s at the limit.
        const interval = 1.2 - (s.opening / DROPWISE_MAX) * 0.95
        let next = { ...s, dropClock: s.dropClock + action.dt }
        while (next.dropClock >= interval) {
          next = { ...dispense(next, config, config.burette.dropVolume), dropClock: next.dropClock - interval, drops: next.drops + 1 }
        }
        return next
      }
      case 'dispenseTo': {
        if (action.volume <= s.volume) return s
        const drops = action.mode === 'dropwise' ? Math.round((action.volume - s.volume) / config.burette.dropVolume) : 0
        return { ...dispense(s, config, action.volume - s.volume), drops: s.drops + Math.max(drops, 1) }
      }
      case 'wobble':
        return { ...s, wobble: action.dx }
      case 'swirl':
        return sample({ ...s, unmixed: 0, wobble: 0 }, config)
      case 'recordEndpoint':
        return { ...s, trials: [...s.trials, { trial: s.trial, reading: round2(s.volume), by: actor === 'agent' ? 'agent' : 'student' }] }
      case 'newTrial':
        return { ...s, opening: 0, volume: 0, unmixed: 0, dropClock: 0, wobble: 0, samples: [], trial: s.trial + 1 }
    }
    return s
  },
  observe(s, action, config) {
    const veq = equivalenceVolume(config)
    const level = colourLevel(config, bulkPH(config, s))
    const base = {
      action: action.type,
      volume: round2(s.volume),
      mixed: s.unmixed < 1e-9,
      colour: colourName(level),
      toEquivalence: round2(veq - s.volume),
    }
    switch (action.type) {
      case 'setTap':
        return { ...base, flow: flowOf(s.opening), nearEndpoint: veq - s.volume < 2 && veq - s.volume > -0.5 }
      case 'swirl':
      case 'dispenseTo':
        return base
      case 'recordEndpoint':
        return { ...base, reading: round2(s.volume), overshoot: round2(s.volume - veq) }
    }
    return null
  },
  tween(s, action) {
    if (action.type === 'swirl') {
      return Array.from({ length: 36 }, (_, i) => ({ type: 'wobble' as const, dx: Math.sin(i / 2.2) * 16 }))
    }
    if (action.type === 'dispenseTo' && action.volume > s.volume) {
      const span = action.volume - s.volume
      if (action.mode === 'dropwise') {
        const drops = Math.max(1, Math.round(span / 0.05))
        // Hold each drop for a few frames so it reads as dripping; long runs of drops go faster.
        const hold = drops > 10 ? 3 : 12
        const steps = Array.from({ length: drops }, (_, i) =>
          Array.from({ length: hold }, () => ({ type: 'dispenseTo' as const, mode: 'dropwise' as const, volume: s.volume + ((i + 1) / drops) * span })),
        ).flat()
        return [{ type: 'setTap' as const, opening: 0.25 }, ...steps, { type: 'setTap' as const, opening: 0 }]
      }
      const frames = 70
      const steps = Array.from({ length: frames }, (_, i) => ({ type: 'dispenseTo' as const, mode: 'stream' as const, volume: s.volume + ((i + 1) / frames) * span }))
      return [{ type: 'setTap' as const, opening: 0.9 }, ...steps, { type: 'setTap' as const, opening: 0 }]
    }
    return []
  },
  anchor(action) {
    if (action.type === 'swirl' || action.type === 'wobble') return 'flask'
    if (action.type === 'recordEndpoint') return 'record'
    if (action.type === 'newTrial') return 'new-trial'
    return 'tap'
  },
  summarize(s, config) {
    const pH = bulkPH(config, s)
    return {
      trial: s.trial,
      buretteReading_mL: round2(s.volume),
      unmixed_mL: round2(s.unmixed),
      tap: flowOf(s.opening),
      colour: colourName(colourLevel(config, pH)),
      pH_mixed: Number(pH.toFixed(2)),
      recordedTrials: s.trials,
    }
  },
  View: TitrationView,
})
