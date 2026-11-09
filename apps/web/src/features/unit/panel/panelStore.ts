import { createKeyedStore } from '../../../lib/keyedStore'
import type { PanelContent } from './types'

/** What's open in each unit's side panel. One item at a time; null = empty. */
const store = createKeyedStore<PanelContent | null>(null)

export const usePanel = store.use
export const openInPanel = (offeringId: string, content: PanelContent) => store.set(offeringId, content)
export const closePanel = (offeringId: string) => store.set(offeringId, null)
