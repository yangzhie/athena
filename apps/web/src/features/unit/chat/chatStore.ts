import { asApiError, type ApiError } from '../../../api/client'
import { answerQuestion, continueSession, getSession, sendSessionMessage, type AnswerInput } from '../../../api/sessions'
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

/** Fetch the session's messages. Without `refresh`, a thread already loaded is reused. */
export async function loadThread(offeringId: string, sessionId: string, { refresh = false } = {}) {
  const current = store.get(sessionId)
  if (current.sending || (current.status === 'ready' && !refresh)) return
  try {
    const { session, messages } = await getSession(offeringId, sessionId)
    if (store.get(sessionId).sending) return  // a turn started meanwhile; it brings its own messages
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

/**
 * Run one tutor turn: show the learner's part (if any) and a "thinking" bubble at once,
 * then swap in what the API stored.
 */
async function turn(
  sessionId: string,
  learnerText: string | null,
  request: (signal: AbortSignal) => Promise<ChatMessage[]>,
  answerFor?: string,
) {
  const t = store.get(sessionId)
  if (t.sending || t.status !== 'ready') return
  const now = new Date().toISOString()
  const learner: ChatMessage | null =
    learnerText === null ? null : { id: tempId(), role: 'learner', content: learnerText, answerFor, createdAt: now }
  const pending: ChatMessage = { id: tempId(), role: 'tutor', content: '', createdAt: now }
  const temp = new Set([pending.id, ...(learner ? [learner.id] : [])])
  store.set(sessionId, { ...t, messages: [...t.messages, ...(learner ? [learner] : []), pending], sending: true, error: undefined })

  const controller = new AbortController()
  controllers.set(sessionId, controller)
  try {
    const saved = await request(controller.signal)
    const cur = store.get(sessionId)
    store.set(sessionId, { ...cur, messages: [...cur.messages.filter((m) => !temp.has(m.id)), ...saved], sending: false })
  } catch (e) {
    const cur = store.get(sessionId)
    const stopped = e instanceof DOMException && e.name === 'AbortError'
    store.set(sessionId, {
      ...cur,
      // Drop the thinking bubble; an unsent answer is dropped too so the question stays open.
      messages: cur.messages.filter((m) => m.id !== pending.id && !(learner?.answerFor && m.id === learner.id)),
      sending: false,
      error: stopped ? undefined : asApiError(e),
    })
  } finally {
    controllers.delete(sessionId)
  }
}

export function sendMessage(offeringId: string, sessionId: string, text: string) {
  return turn(sessionId, text, (signal) => sendSessionMessage(offeringId, sessionId, text, signal))
}

/** Answers the tutor's question. The server echoes the learner's answer as their message. */
export function answer(offeringId: string, sessionId: string, input: AnswerInput) {
  return turn(sessionId, input.shown, (signal) => answerQuestion(offeringId, sessionId, input, signal), input.questionId)
}

export function continueLearning(offeringId: string, sessionId: string, activityId: string) {
  return turn(sessionId, null, (signal) => continueSession(offeringId, sessionId, activityId, signal))
}

/** Stop waiting for the reply. The server may still save it; it appears on the next load. */
export function stopWaiting(sessionId: string) {
  controllers.get(sessionId)?.abort()
}
