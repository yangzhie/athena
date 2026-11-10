import type { TitrationConfig } from '../../contracts'

/**
 * Ideal strong acid / strong base titration. Activity effects and water's own
 * ions are ignored except exactly at equivalence; good enough to show the
 * shape of the curve and the indicator colour, not for real measurements.
 */
export function pHAfter(config: TitrationConfig, baseML: number): number {
  const acidMol = (config.analyte.concentration * config.analyte.volume) / 1000
  const baseMol = (config.titrant.concentration * baseML) / 1000
  const litres = (config.analyte.volume + baseML) / 1000
  const excess = (baseMol - acidMol) / litres
  if (Math.abs(excess) < 1e-7) return 7
  return excess < 0 ? -Math.log10(-excess) : 14 + Math.log10(excess)
}

/** Volume of titrant that exactly neutralises the analyte. */
export function equivalenceVolume(config: TitrationConfig): number {
  return (config.analyte.concentration * config.analyte.volume) / config.titrant.concentration
}

export type Colour = 'colourless' | 'faint pink' | 'deep pink'

/** 0 = colourless … 1 = deepest colour the indicator reaches. */
export function colourLevel(config: TitrationConfig, pH: number): number {
  const [lo, hi] = config.indicator.transition
  return Math.min(1, Math.max(0, (pH - lo) / (hi + 1.5 - lo)))
}

export function colourName(level: number): Colour {
  return level <= 0 ? 'colourless' : level < 0.72 ? 'faint pink' : 'deep pink'
}

/** The analyte concentration the student would calculate from a recorded titre. */
export function titrantFromReading(config: TitrationConfig, readingML: number) {
  return (config.analyte.concentration * config.analyte.volume) / readingML
}
