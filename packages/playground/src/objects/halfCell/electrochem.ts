import type { HalfCellConfig, ObjectId } from '../../contracts'
import type { Wiring } from '../types'

/** RT/F · ln 10 at 25 °C, in volts. */
const NERNST_SLOPE = 0.05916

/** Reduction potential of M^n+ | M at a given ion concentration (Nernst, ideal solution, 25 °C). */
export function electrodePotential(cfg: Pick<HalfCellConfig, 'standardPotential' | 'electrons'>, concentration: number) {
  return cfg.standardPotential + (NERNST_SLOPE / cfg.electrons) * Math.log10(concentration)
}

/** What a half-cell exposes through its electrode. */
export interface Electrode {
  cell: ObjectId
  metal: string
  ion: string
  concentration: number
  potential: number
  /** Half-cells this one is joined to by a salt bridge. */
  bridgedTo: ObjectId[]
}

/** What a salt-bridge end exposes: the beaker its other end dips into. */
export interface BridgeEnd {
  otherCell: ObjectId | null
}

/** What a voltmeter shows. Only a closed circuit gives a reading. */
export interface MeterReading {
  volts: number
  circuit: 'unplugged' | 'same-cell' | 'open' | 'closed'
  red: Electrode | null
  black: Electrode | null
}

export function measure(w: Wiring): MeterReading {
  const at = (plug: string) => {
    const ref = w.peers(plug)[0]
    return ref ? ((w.read(ref) as Electrode | undefined) ?? null) : null
  }
  const red = at('v')
  const black = at('com')
  if (!red || !black) return { volts: 0, circuit: 'unplugged', red, black }
  if (red.cell === black.cell) return { volts: 0, circuit: 'same-cell', red, black }
  if (!red.bridgedTo.includes(black.cell)) return { volts: 0, circuit: 'open', red, black }
  return { volts: red.potential - black.potential, circuit: 'closed', red, black }
}

export const formatVolts = (v: number) => `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(3)}`
export const formatConc = (c: number) => (c >= 0.1 ? c.toFixed(2) : c.toPrecision(2)) + ' M'
