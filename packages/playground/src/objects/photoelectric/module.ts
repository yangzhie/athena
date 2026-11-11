import type { Observation, PhotoelectricConfig } from '../../contracts'
import { defineModule } from '../types'
import { PhotoelectricView } from './PhotoelectricView'
import { frequencyOf, photocurrent, stoppingVoltage, type PhotoReading } from './physics'
import { s } from '../../core/schema'

export interface PhotoelectricState {
  line: number
  intensity: number
  voltage: number
}

/** The retarding voltage the supply can reach, V. */
export const MAX_VOLTAGE = 2.5
/** Lamp distance from the tube, cm: intensity goes as (NEAR / d)², so 1 at NEAR and 0.25 at FAR. */
export const LAMP_RANGE: [number, number] = [10, 20]
export const intensityAt = (cm: number) => (LAMP_RANGE[0] / cm) ** 2
export const distanceFor = (intensity: number) => LAMP_RANGE[0] / Math.sqrt(intensity)

const round2 = (x: number) => Math.round(x * 100) / 100

export function readingOf(state: PhotoelectricState, config: PhotoelectricConfig): PhotoReading {
  const line = config.lines[state.line]
  return {
    line: line.label,
    wavelength: line.wavelength,
    frequency: frequencyOf(line.wavelength),
    intensity: state.intensity,
    voltage: state.voltage,
    current: photocurrent(config, line.wavelength, state.intensity, state.voltage),
    v0: stoppingVoltage(config, line.wavelength),
  }
}

export const photoelectricModule = defineModule<'photoelectric', PhotoelectricState>({
  type: 'photoelectric',
  label: 'Photoelectric rig',
  about: {
    summary:
      'A phototube lit by one line of a mercury lamp at a time, worked by hand: the student slides a selector along the spectrum to pick the line, slides the lamp along its rail (intensity goes as 1/d², from 1 at 10 cm to 0.25 at 20 cm), and turns a knob for the retarding voltage, reading the photocurrent on a nanoammeter. Its `data` plug carries the reading to a photo log `in` socket (pre-plug it with the scene `wiring`). Ideal model: V₀ = (hf − φ)/e, current falling linearly to zero at V₀, no current below the threshold frequency.',
    config: s.object({
      cathode: s.object({ label: s.string('e.g. "Potassium"'), workFunction: s.number('eV', 1, 6) }),
      lines: s.array(s.object({ label: s.string('e.g. "UV"'), wavelength: s.number('nm', 200, 800) }), 'Lamp lines the student can pick', 2, 8),
      maxCurrent: s.number('nA at full intensity and no retarding voltage', 1, 500),
    }),
    actions: {
      selectLine: '{index}: light the tube with this lamp line',
      setIntensity: '{level}: 0.25 … 1 (moves the lamp to the matching distance)',
      setVoltage: `{volts}: retarding voltage, 0 … ${MAX_VOLTAGE} V`,
    },
    observes: {
      on: ['selectLine', 'setIntensity'],
      fields: {
        line: 'label of the lamp line',
        wavelength: 'nm',
        intensity: '0.25 … 1',
        current: 'nA on the meter at the present voltage',
        belowThreshold: 'this light frees no electrons at any intensity',
      },
    },
  },
  width: 460,
  ports: {
    data: { kind: 'data', role: 'plug', at: { x: 460, y: 70 }, rest: { x: 500, y: 110 }, look: 'data', label: 'data' },
  },
  init: () => ({ line: 0, intensity: 1, voltage: 0 }),
  edits: ['selectLine', 'setIntensity', 'setVoltage'],
  reduce(state, action, config) {
    switch (action.type) {
      case 'selectLine':
        return action.index >= 0 && action.index < config.lines.length ? { ...state, line: action.index } : state
      case 'setIntensity':
        return { ...state, intensity: Math.round(Math.min(1, Math.max(0.25, action.level)) * 100) / 100 }
      case 'setVoltage':
        return { ...state, voltage: round2(Math.min(MAX_VOLTAGE, Math.max(0, action.volts))) }
    }
    return state
  },
  read: (state, config, port) => (port === 'data' ? readingOf(state, config) : undefined),
  observe(state, action, config): Observation | null {
    if (action.type !== 'selectLine' && action.type !== 'setIntensity') return null
    const r = readingOf(state, config)
    return { action: action.type, line: r.line, wavelength: r.wavelength, intensity: r.intensity, current: r.current, belowThreshold: r.v0 <= 0 }
  },
  // The hand turns the knob and slides the lamp rather than jumping them.
  tween(state, action) {
    const frames = 40
    if (action.type === 'setVoltage')
      return Array.from({ length: frames }, (_, i) => ({ type: 'setVoltage' as const, volts: state.voltage + ((i + 1) / frames) * (action.volts - state.voltage) }))
    if (action.type === 'setIntensity') {
      const [from, to] = [distanceFor(state.intensity), distanceFor(Math.min(1, Math.max(0.25, action.level)))]
      return Array.from({ length: frames }, (_, i) => ({ type: 'setIntensity' as const, level: intensityAt(from + ((i + 1) / frames) * (to - from)) }))
    }
    return []
  },
  anchor(action) {
    if (action.type === 'selectLine') return `line-${action.index}`
    if (action.type === 'setIntensity') return 'lamp'
    return 'knob'
  },
  summarize(state, config) {
    const r = readingOf(state, config)
    return {
      cathode: `${config.cathode.label}, φ = ${config.cathode.workFunction} eV`,
      line: `${r.line} ${r.wavelength} nm`,
      intensity: r.intensity,
      retardingVoltage_V: r.voltage,
      current_nA: r.current,
    }
  },
  View: PhotoelectricView,
})
