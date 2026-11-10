import { useMemo } from 'react'
import { createPersistedStore } from '../../../lib/persistedStore'
import type { LearningSession } from '../../../types'
import { deleteThread, seedThread } from '../chat/chatStore'

/**
 * The student's sessions per unit. Kept in this browser for now; moves to
 * apps/api (scoped to the signed-in student) in the next step.
 */
const store = createPersistedStore<Record<string, LearningSession[]>>('athena.sessions', {})

/** Most recently used first. */
export function useSessions(offeringId: string): LearningSession[] {
  const all = store.use()
  return useMemo(
    () => [...(all[offeringId] ?? [])].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
    [all, offeringId],
  )
}

export function useSession(offeringId: string, sessionId: string): LearningSession | undefined {
  return useSessions(offeringId).find((s) => s.id === sessionId)
}

function update(offeringId: string, fn: (list: LearningSession[]) => LearningSession[]) {
  store.set((all) => ({ ...all, [offeringId]: fn(all[offeringId] ?? []) }))
}

export function createSession(offeringId: string, goal: string): LearningSession {
  const now = new Date().toISOString()
  const clean = goal.trim().replace(/\s+/g, ' ')
  const session: LearningSession = {
    id: crypto.randomUUID(),
    offeringId,
    goal: clean,
    title: clean.length > 60 ? `${clean.slice(0, 57)}…` : clean,
    createdAt: now,
    updatedAt: now,
    shared: false,
  }
  update(offeringId, (list) => [...list, session])
  // The tutor opens the session: Athena asks first rather than waiting for a question.
  seedThread(session.id, {
    id: `${session.id}-intro`,
    role: 'tutor',
    content: `Let’s work on “${clean}”. To start, tell me what you already know about it, or where you get stuck. I’ll pitch things from there.`,
    createdAt: now,
  })
  return session
}

export function renameSession(offeringId: string, sessionId: string, title: string) {
  const clean = title.trim()
  if (!clean) return
  update(offeringId, (list) => list.map((s) => (s.id === sessionId ? { ...s, title: clean.slice(0, 80) } : s)))
}

export function touchSession(offeringId: string, sessionId: string) {
  const now = new Date().toISOString()
  update(offeringId, (list) => list.map((s) => (s.id === sessionId ? { ...s, updatedAt: now } : s)))
}

export function deleteSession(offeringId: string, sessionId: string) {
  update(offeringId, (list) => list.filter((s) => s.id !== sessionId))
  deleteThread(sessionId)
}
