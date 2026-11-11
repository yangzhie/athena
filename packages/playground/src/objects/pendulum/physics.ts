/** Period of a simple pendulum, s, with the first two large-amplitude corrections to 2π√(L/g). */
export function periodOf(length: number, g: number, amplitudeDeg: number) {
  const a = (amplitudeDeg * Math.PI) / 180
  return 2 * Math.PI * Math.sqrt(length / g) * (1 + a ** 2 / 16 + (11 * a ** 4) / 3072)
}

/** What the photogate reads from the pendulum it is clipped onto. */
export interface SwingReading {
  length: number // m
  mass: number // g
  amplitude: number // degrees
  period: number // s, to the millisecond
}
