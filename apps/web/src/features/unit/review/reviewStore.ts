import { createPersistedStore } from '../../../lib/persistedStore'

/**
 * A lecturer's decision on one proposed clip, plus any edits.
 * Kept in this browser for the PoC; the API will store these and update clips.json.
 */
export interface ClipDecision {
  status: 'approved' | 'rejected'
  title?: string
  startS?: number
  endS?: number
}

type Decisions = Record<string, ClipDecision>

const store = createPersistedStore<Decisions>('athena.clipReview', {})

export const useDecisions = store.use

export function decide(clipId: string, status: ClipDecision['status']) {
  store.set((d) => ({ ...d, [clipId]: { ...d[clipId], status } }))
}

/** Edits keep the current status, or count as approval if the clip was undecided. */
export function editClip(clipId: string, edit: Pick<ClipDecision, 'title' | 'startS' | 'endS'>) {
  store.set((d) => ({ ...d, [clipId]: { ...d[clipId], ...edit, status: d[clipId]?.status ?? 'approved' } }))
}

export function approveAll(clipIds: string[]) {
  store.set((d) => {
    const next = { ...d }
    for (const id of clipIds) if (!next[id]) next[id] = { status: 'approved' }
    return next
  })
}

export function resetClip(clipId: string) {
  store.set((d) => {
    const next = { ...d }
    delete next[clipId]
    return next
  })
}
