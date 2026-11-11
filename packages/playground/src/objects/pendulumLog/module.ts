import type { Actor, Observation, PendulumLogConfig } from '../../contracts'
import { fitLine } from '../photoelectric/physics'
import type { SwingReading } from '../pendulum/physics'
import { defineModule, type Wiring } from '../types'
import { PendulumLogView } from './PendulumLogView'
import { s } from '../../core/schema'

export const STANDARD_G = 9.81
/** Above this release angle the small-angle formula visibly fails. */
const SMALL_ANGLE = 15

export interface PeriodRow extends SwingReading {
  by: Actor
}

export interface GFit {
  slope: number // s²/m, = 4π²/g
  intercept: number // s²
  g: number
  points: number // distinct lengths
  largeAngle: boolean
}

export interface PendulumLogState {
  rows: PeriodRow[]
  fit: GFit | null
  /** What happened at the last recording, kept for checks. */
  last: { connected: boolean; reading: SwingReading | null; sameOtherMass: boolean } | null
}

/** What the plugged-in photogate shows: null without a timer, `undefined` reading if its gate hangs free. */
export function connectedTimer(w: Wiring): { connected: boolean; reading: SwingReading | null } {
  const ref = w.peers('in')[0]
  return ref ? { connected: true, reading: (w.read(ref) as SwingReading | null) ?? null } : { connected: false, reading: null }
}

const sig = (x: number, digits = 3) => Number(x.toPrecision(digits))

export const pendulumLogModule = defineModule<'pendulum-log', PendulumLogState>({
  type: 'pendulum-log',
  label: 'Pendulum log',
  about: {
    summary:
      'A lab notebook for the photogate whose data cable is plugged into its `in` socket. Record T stores the period with the length, mass and release angle (recording the same length and mass again replaces the row, so a reading can be retaken at a smaller angle). Fit g draws T² against L and gives g = 4π² / slope.',
    config: s.empty(),
    actions: { recordPeriod: '{}: record the period the photogate shows', fitG: '{}: fit T² against L' },
    observes: {
      on: ['recordPeriod', 'fitG'],
      fields: {
        connected: 'recordPeriod: a photogate is plugged in',
        gated: 'recordPeriod: its sensor is clipped onto a pendulum',
        length: 'recordPeriod: m',
        mass: 'recordPeriod: g',
        amplitude: 'recordPeriod: release angle, degrees',
        period: 'recordPeriod: s',
        sameOtherMass: 'recordPeriod: same length and angle already recorded with another mass, same period',
        points: 'fitG: distinct lengths',
        gErrorPct: 'fitG: |g − 9.81| as a percentage',
        largeAngle: `fitG: some points were released above ${SMALL_ANGLE}°`,
      },
    },
  },
  width: 440,
  ports: {
    in: { kind: 'data', role: 'socket', at: { x: 0, y: 19 } },
  },
  init: (): PendulumLogState => ({ rows: [], fit: null, last: null }),
  edits: ['recordPeriod', 'fitG'],
  reduce(state, action, _config: PendulumLogConfig, actor, wiring) {
    if (action.type === 'fitG') {
      const points = new Set(state.rows.map((r) => r.length)).size
      if (points < 2) return { ...state, fit: null }
      const line = fitLine(state.rows.map((r) => ({ x: r.length, y: r.period ** 2 })))
      const g = (4 * Math.PI ** 2) / line.slope
      return { ...state, fit: { ...line, g, points, largeAngle: state.rows.some((r) => r.amplitude > SMALL_ANGLE) } }
    }
    if (action.type !== 'recordPeriod') return state
    const { connected, reading } = connectedTimer(wiring)
    if (!reading) return { ...state, last: { connected, reading, sameOtherMass: false } }
    const same = (r: SwingReading) => r.length === reading.length && r.amplitude === reading.amplitude
    const sameOtherMass = state.rows.some((r) => same(r) && r.mass !== reading.mass && Math.abs(r.period - reading.period) < 0.002)
    const retaken = (r: SwingReading) => r.length === reading.length && r.mass === reading.mass
    const rows = [...state.rows.filter((r) => !retaken(r)), { ...reading, by: actor }].sort((a, b) => a.length - b.length)
    return { rows, fit: null, last: { connected, reading, sameOtherMass } }
  },
  observe(state, action): Observation | null {
    if (action.type === 'fitG') {
      const fit = state.fit
      if (!fit) return { action: 'fitG', points: new Set(state.rows.map((r) => r.length)).size }
      return { action: 'fitG', points: fit.points, gErrorPct: sig((Math.abs(fit.g - STANDARD_G) / STANDARD_G) * 100, 2), largeAngle: fit.largeAngle }
    }
    if (action.type !== 'recordPeriod' || !state.last) return null
    const { connected, reading, sameOtherMass } = state.last
    if (!reading) return { action: 'recordPeriod', connected, gated: false }
    return { action: 'recordPeriod', connected, gated: true, ...reading, sameOtherMass }
  },
  anchor: (action) => (action.type === 'fitG' ? 'fit' : 'record'),
  summarize(state, _config, wiring) {
    return {
      timerConnected: connectedTimer(wiring).connected,
      rows: state.rows.map(({ length, mass, amplitude, period }) => ({ length_m: length, mass_g: mass, amplitude_deg: amplitude, period_s: period })),
      fit: state.fit && { g: sig(state.fit.g), points: state.fit.points },
    }
  },
  View: PendulumLogView,
})
