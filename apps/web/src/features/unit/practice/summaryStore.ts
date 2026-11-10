import { getSrsSummary, type SrsSummary } from '../../../api/srs'
import { createKeyedStore } from '../../../lib/keyedStore'

/** Latest SRS summary per unit, for the due badge. null = unknown (loading or API down). */
const store = createKeyedStore<SrsSummary | null>(null)

export const useSrsSummary = store.use

export async function refreshSrsSummary(offeringId: string) {
  try {
    store.set(offeringId, await getSrsSummary(offeringId))
  } catch {
    store.set(offeringId, null)
  }
}
