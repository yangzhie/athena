import type { ForceCurvePoint } from '../../contracts'

export type Regime = 'repulsive' | 'balanced' | 'attractive' | 'negligible'

export const REGIME_LABEL: Record<Regime, string> = {
  repulsive: 'Repulsion',
  balanced: 'Balanced',
  attractive: 'Attraction',
  negligible: 'Almost no force',
}

/** Linear interpolation between the scene's key points; clamps outside them. */
export function forceAt(curve: ForceCurvePoint[], r: number): number {
  if (r <= curve[0].r) return curve[0].f
  for (let i = 1; i < curve.length; i++) {
    const a = curve[i - 1]
    const b = curve[i]
    if (r <= b.r) return a.f + ((r - a.r) / (b.r - a.r)) * (b.f - a.f)
  }
  return curve[curve.length - 1].f
}

/** Where the net force crosses zero (repulsion → attraction). */
export function equilibrium(curve: ForceCurvePoint[]): number | null {
  for (let i = 1; i < curve.length; i++) {
    const a = curve[i - 1]
    const b = curve[i]
    if (a.f > 0 && b.f <= 0) return a.r + (a.f / (a.f - b.f)) * (b.r - a.r)
  }
  return null
}

export function regimeAt(curve: ForceCurvePoint[], r: number): Regime {
  const eq = equilibrium(curve)
  if (eq !== null && Math.abs(r - eq) <= 0.012) return 'balanced'
  const f = forceAt(curve, r)
  if (f > 0) return 'repulsive'
  const strongest = Math.max(...curve.map((p) => -p.f))
  return -f < strongest * 0.05 ? 'negligible' : 'attractive'
}
