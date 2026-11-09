import type { Offering } from '../types'
import { enrolledOfferings } from '../mocks/spaces'

/** Offerings the current student is enrolled in. */
export async function listEnrolledOfferings(): Promise<Offering[]> {
  return enrolledOfferings
}

export async function getEnrolledOffering(id: string): Promise<Offering | undefined> {
  return enrolledOfferings.find((o) => o.id === id)
}
