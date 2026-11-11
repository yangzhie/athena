import type { Actor, Observation, PhotoLogConfig } from '../../contracts'
import { fitLine, PLANCK, type PhotoReading } from '../photoelectric/physics'
import { defineModule, type Wiring } from '../types'
import { PhotoLogView } from './PhotoLogView'
import { s } from '../../core/schema'

const ELEMENTARY_CHARGE = 1.602176634e-19

export interface StopRow {
  line: string
  wavelength: number
  frequency: number // Hz
  intensity: number
  v0: number // the voltage recorded as V₀
  by: Actor
}

export interface LineFit {
  slope: number // V/Hz, = h/e
  intercept: number // V, = −φ/e
  points: number // distinct frequencies
}

export interface PhotoLogState {
  rows: StopRow[]
  fit: LineFit | null
  /** What happened at the last recording, kept for checks. */
  last: { reading: PhotoReading | null; repeatSame: boolean } | null
}

export function connectedRig(w: Wiring): PhotoReading | null {
  const ref = w.peers('in')[0]
  return ref ? ((w.read(ref) as PhotoReading | undefined) ?? null) : null
}

/** h from the fitted slope, J·s. */
export const planckOf = (fit: LineFit) => fit.slope * ELEMENTARY_CHARGE

const sig = (x: number, digits = 3) => Number(x.toPrecision(digits))

export const photoLogModule = defineModule<'photo-log', PhotoLogState>({
  type: 'photo-log',
  label: 'Photo log',
  about: {
    summary:
      "A lab notebook for the photoelectric rig whose data cable is plugged into its `in` socket. Record V₀ stores the rig's present voltage as the stopping voltage of its line (only once the current reads 0.0 nA; recording the same line and intensity again replaces it). Fit line draws the least-squares line of V₀ against frequency and reports h = e × slope and the work function.",
    config: s.empty(),
    actions: { recordStop: '{}: record the voltage as V₀ for the lit line', fitLine: '{}: fit V₀ against frequency' },
    observes: {
      on: ['recordStop', 'fitLine'],
      fields: {
        connected: 'recordStop: a rig is plugged in',
        belowThreshold: 'recordStop: the light frees no electrons, so there is no V₀',
        current: 'recordStop: nA on the meter (V₀ needs 0.0)',
        overshoot: 'recordStop: recorded voltage minus the true V₀, V (large means the current was already zero lower down)',
        line: 'recordStop: lamp line label',
        intensity: 'recordStop: 0.25 … 1',
        repeatSame: 'recordStop: this line was already recorded at another intensity with the same V₀ (within 0.03 V)',
        points: 'fitLine: distinct frequencies in the fit',
        errorPct: 'fitLine: |h − 6.626e-34| as a percentage',
        workFunction: 'fitLine: φ from the intercept, eV',
      },
    },
  },
  width: 460,
  ports: {
    in: { kind: 'data', role: 'socket', at: { x: 0, y: 19 } },
  },
  init: (): PhotoLogState => ({ rows: [], fit: null, last: null }),
  edits: ['recordStop', 'fitLine'],
  reduce(state, action, _config: PhotoLogConfig, actor, wiring) {
    if (action.type === 'fitLine') {
      const points = state.rows.map((r) => ({ x: r.frequency, y: r.v0 }))
      const distinct = new Set(state.rows.map((r) => r.wavelength)).size
      return { ...state, fit: distinct >= 2 ? { ...fitLine(points), points: distinct } : null }
    }
    if (action.type !== 'recordStop') return state
    const m = connectedRig(wiring)
    // No rig, no electrons or a current still flowing: nothing worth writing down; the check explains why.
    if (!m || m.v0 <= 0 || m.current > 0) return { ...state, last: { reading: m, repeatSame: false } }
    const repeatSame = state.rows.some((r) => r.wavelength === m.wavelength && r.intensity !== m.intensity && Math.abs(r.v0 - m.voltage) <= 0.03)
    const row: StopRow = { line: m.line, wavelength: m.wavelength, frequency: m.frequency, intensity: m.intensity, v0: m.voltage, by: actor }
    const rows = [...state.rows.filter((r) => r.wavelength !== m.wavelength || r.intensity !== m.intensity), row].sort((a, b) => a.frequency - b.frequency)
    return { rows, fit: null, last: { reading: m, repeatSame } }
  },
  observe(state, action): Observation | null {
    if (action.type === 'fitLine') {
      const fit = state.fit
      if (!fit) return { action: 'fitLine', points: new Set(state.rows.map((r) => r.wavelength)).size }
      return {
        action: 'fitLine',
        points: fit.points,
        errorPct: sig((Math.abs(planckOf(fit) - PLANCK) / PLANCK) * 100, 2),
        workFunction: sig(-fit.intercept),
      }
    }
    if (action.type !== 'recordStop') return null
    const m = state.last?.reading
    if (!m) return { action: 'recordStop', connected: false }
    return {
      action: 'recordStop',
      connected: true,
      belowThreshold: m.v0 <= 0,
      current: m.current,
      overshoot: Number((m.voltage - m.v0).toFixed(3)),
      line: m.line,
      intensity: m.intensity,
      repeatSame: state.last?.repeatSame ?? false,
    }
  },
  anchor: (action) => (action.type === 'fitLine' ? 'fit' : 'record'),
  summarize(state, _config, wiring) {
    return {
      rigConnected: Boolean(wiring.peers('in').length),
      rows: state.rows.map((r) => ({ line: r.line, frequency_1e14Hz: sig(r.frequency / 1e14), intensity: r.intensity, v0_V: r.v0 })),
      fit: state.fit && { h_Js: sig(planckOf(state.fit)), workFunction_eV: sig(-state.fit.intercept), points: state.fit.points },
    }
  },
  View: PhotoLogView,
})
