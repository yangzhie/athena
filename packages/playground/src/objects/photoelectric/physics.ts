import type { PhotoelectricConfig } from '../../contracts'

/** Planck's constant over the elementary charge, V·s. */
export const H_OVER_E = 4.135667e-15
/** Planck's constant, J·s. */
export const PLANCK = 6.62607e-34
const C = 2.99792458e8

export const frequencyOf = (wavelengthNm: number) => C / (wavelengthNm * 1e-9)

/** Energy of one photon of this wavelength, eV. */
export const photonEnergy = (wavelengthNm: number) => H_OVER_E * frequencyOf(wavelengthNm)

/** V₀ = (hf − φ)/e. Zero or below means the light frees no electrons. */
export const stoppingVoltage = (config: PhotoelectricConfig, wavelengthNm: number) => photonEnergy(wavelengthNm) - config.cathode.workFunction

/**
 * Photocurrent in nA. Saturated at zero or accelerating voltage, then falling
 * linearly to zero at V₀ (electrons leave with energies spread up to hf − φ).
 * Shown to 0.1 nA, as the meter would.
 */
export function photocurrent(config: PhotoelectricConfig, wavelengthNm: number, intensity: number, volts: number) {
  const v0 = stoppingVoltage(config, wavelengthNm)
  if (v0 <= 0) return 0
  const saturated = config.maxCurrent * intensity
  const i = volts <= 0 ? saturated : volts >= v0 ? 0 : saturated * (1 - volts / v0)
  return Math.round(i * 10) / 10
}

/** What the rig sends down its data cable. */
export interface PhotoReading {
  line: string
  wavelength: number
  frequency: number // Hz
  intensity: number
  voltage: number
  current: number // nA, as displayed
  /** The true stopping voltage, kept for checks; ≤ 0 below the threshold frequency. */
  v0: number
}

/** Least-squares line y = slope·x + intercept. */
export function fitLine(points: { x: number; y: number }[]) {
  const n = points.length
  const mx = points.reduce((s, p) => s + p.x, 0) / n
  const my = points.reduce((s, p) => s + p.y, 0) / n
  const sxx = points.reduce((s, p) => s + (p.x - mx) ** 2, 0)
  const slope = points.reduce((s, p) => s + (p.x - mx) * (p.y - my), 0) / sxx
  return { slope, intercept: my - slope * mx }
}

/** A colour for a lamp line, so the beam looks like the light it stands for. */
export function lineColour(wavelengthNm: number) {
  if (wavelengthNm < 380) return '#7c3aed'
  if (wavelengthNm < 420) return '#8b5cf6'
  if (wavelengthNm < 480) return '#3b82f6'
  if (wavelengthNm < 560) return '#22c55e'
  if (wavelengthNm < 590) return '#eab308'
  return '#f97316'
}
