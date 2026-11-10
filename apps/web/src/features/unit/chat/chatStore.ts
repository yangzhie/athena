import { asApiError, type ApiError } from '../../../api/client'
import { getSession, sendSessionMessage } from '../../../api/sessions'
import { createKeyedStore } from '../../../lib/keyedStore'
import type { ChatMessage, LearningSession } from '../../../types'

/** One learning session's chat, loaded from and saved by apps/api. */
export interface Thread {
  status: 'loading' | 'ready' | 'missing' | 'error'
  session?: LearningSession
  messages: ChatMessage[]
  /** Waiting for the tutor's reply. */
  sending: boolean
  error?: ApiError
}

const EMPTY: Thread = { status: 'loading', messages: [], sending: false }
const store = createKeyedStore<Thread>(EMPTY)
const controllers = new Map<string, AbortController>()

export const useThread = store.use

export async function loadThread(offeringId: string, sessionId: string) {
  const current = store.get(sessionId)
  if (current.status === 'ready' || current.sending) return
  try {
    const { session, messages } = await getSession(offeringId, sessionId)
    store.set(sessionId, { status: 'ready', session, messages, sending: false })
  } catch (e) {
    const error = asApiError(e)
    store.set(sessionId, { ...EMPTY, status: error.status === 404 ? 'missing' : 'error', error })
  }
}

export function seedThread(session: LearningSession, messages: ChatMessage[]) {
  store.set(session.id, { status: 'ready', session, messages, sending: false })
}

export function updateThreadSession(session: LearningSession) {
  const t = store.get(session.id)
  if (t.session) store.set(session.id, { ...t, session })
}

export function forgetThread(sessionId: string) {
  controllers.get(sessionId)?.abort()
  store.set(sessionId, { ...EMPTY, status: 'missing' })
}

let seq = 0
const tempId = () => `pending-${Date.now()}-${seq++}`

/** Show the learner's message and a "thinking" tutor bubble, then swap in what the API stored. */
export async function sendMessage(offeringId: string, sessionId: string, text: string) {
  const t = store.get(sessionId)
  if (t.sending || t.status !== 'ready') return
  const now = new Date().toISOString()
  const learner: ChatMessage = { id: tempId(), role: 'learner', content: text, createdAt: now }
  const pending: ChatMessage = { id: tempId(), role: 'tutor', content: '', createdAt: now }
  store.set(sessionId, { ...t, messages: [...t.messages, learner, pending], sending: true, error: undefined })

  const controller = new AbortController()
  controllers.set(sessionId, controller)
  try {
    const saved = await sendSessionMessage(offeringId, sessionId, text, controller.signal)
    const cur = store.get(sessionId)
    store.set(sessionId, {
      ...cur,
      messages: [...cur.messages.filter((m) => m.id !== learner.id && m.id !== pending.id), ...saved],
      sending: false,
    })
  } catch (e) {
    const cur = store.get(sessionId)
    const stopped = e instanceof DOMException && e.name === 'AbortError'
    store.set(sessionId, {
      ...cur,
      // Keep what the learner typed visible; drop the empty tutor bubble.
      messages: cur.messages.filter((m) => m.id !== pending.id),
      sending: false,
      error: stopped ? undefined : asApiError(e),
    })
  } finally {
    controllers.delete(sessionId)
  }
}

/** Stop waiting for the reply. The server may still save it; it appears on the next load. */
export function stopWaiting(sessionId: string) {
  controllers.get(sessionId)?.abort()
}
