import { createPersistedStore } from '../../../lib/persistedStore'
import type { LearningSession } from '../../../types'

/**
 * When this student last opened each session, for the "new reply from your lecturer"
 * marker. A per-browser convenience (kept in localStorage); nothing depends on it.
 */
const store = createPersistedStore<Record<string, string>>('athena.sessionsSeen', {})

export const useSeen = store.use

export function markSeen(sessionId: string) {
  store.set((seen) => ({ ...seen, [sessionId]: new Date().toISOString() }))
}

export function hasNewReply(session: LearningSession, seen: Record<string, string>): boolean {
  if (!session.lastLecturerReplyAt) return false
  const last = seen[session.id]
  return !last || session.lastLecturerReplyAt > last
}
