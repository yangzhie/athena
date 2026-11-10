import * as api from '../../../api/sessions'
import { asApiError, type ApiError } from '../../../api/client'
import { createKeyedStore } from '../../../lib/keyedStore'
import type { LearningSession } from '../../../types'
import { forgetThread, seedThread } from '../chat/chatStore'

/** The student's sessions per unit, from apps/api. */
export interface SessionList {
  status: 'loading' | 'ready' | 'error'
  sessions: LearningSession[]
  error?: ApiError
}

const store = createKeyedStore<SessionList>({ status: 'loading', sessions: [] })

export const useSessionList = store.use

export async function refreshSessions(offeringId: string) {
  try {
    store.set(offeringId, { status: 'ready', sessions: await api.listSessions(offeringId) })
  } catch (e) {
    store.set(offeringId, { ...store.get(offeringId), status: 'error', error: asApiError(e) })
  }
}

function upsert(session: LearningSession) {
  const list = store.get(session.offeringId).sessions.filter((s) => s.id !== session.id)
  const sessions = [session, ...list].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  store.set(session.offeringId, { status: 'ready', sessions })
}

/** Creates the session (the API adds the tutor's opening message) and returns it. */
export async function createSession(offeringId: string, goal: string): Promise<LearningSession> {
  const { session, messages } = await api.createSession(offeringId, goal)
  seedThread(session, messages)
  upsert(session)
  return session
}

export async function renameSession(offeringId: string, sessionId: string, title: string) {
  const session = await api.renameSession(offeringId, sessionId, title)
  upsert(session)
  return session
}

export async function deleteSession(offeringId: string, sessionId: string) {
  await api.deleteSession(offeringId, sessionId)
  const list = store.get(offeringId)
  store.set(offeringId, { ...list, sessions: list.sessions.filter((s) => s.id !== sessionId) })
  forgetThread(sessionId)
}

/** After a message, move the session to the top of the list. */
export function bumpSession(session: LearningSession) {
  upsert({ ...session, updatedAt: new Date().toISOString() })
}

export async function setSharing(offeringId: string, sessionId: string, shared: boolean) {
  const session = shared ? await api.shareSession(offeringId, sessionId) : await api.unshareSession(offeringId, sessionId)
  upsert(session)
  return session
}
