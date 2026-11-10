import { asApiError, type ApiError } from '../../../api/client'
import { generateScene } from '../../../api/playground'
import { answerQuestion, continueSession, getSession, sendSessionMessage, type AnswerInput } from '../../../api/sessions'
import { createKeyedStore } from '../../../lib/keyedStore'
import type { ChatMessage, LearningSession, Offering } from '../../../types'

/** One API-backed learning session, with clearly labelled, local-only Playground messages. */
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
const loads = new Map<string, symbol>()

export const useThread = store.use
export const getThread = store.get

const chronological = (messages: ChatMessage[]) =>
  messages.sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt))

/** Fetch the session's messages. Refreshes retain local demo messages in this browser tab. */
export async function loadThread(offeringId: string, sessionId: string, { refresh = false } = {}) {
  const current = store.get(sessionId)
  if (current.sending || (current.status === 'ready' && current.session?.offeringId === offeringId && !refresh)) return
  const request = Symbol()
  loads.set(sessionId, request)
  try {
    const { session, messages } = await getSession(offeringId, sessionId)
    if (loads.get(sessionId) !== request) return
    const local = store.get(sessionId).messages.filter((m) => m.via === 'playground')
    store.set(sessionId, { status: 'ready', session, messages: chronological([...messages, ...local]), sending: false })
  } catch (e) {
    if (loads.get(sessionId) !== request) return
    const error = asApiError(e)
    const previous = error.status === 404 || error.status === 403 || error.status === 401 ? EMPTY : store.get(sessionId)
    store.set(sessionId, { ...previous, status: error.status === 404 ? 'missing' : 'error', error })
  } finally {
    if (loads.get(sessionId) === request) loads.delete(sessionId)
  }
}

export function seedThread(session: LearningSession, messages: ChatMessage[]) {
  loads.delete(session.id)
  store.set(session.id, { status: 'ready', session, messages, sending: false })
}

export function updateThreadSession(session: LearningSession) {
  const t = store.get(session.id)
  if (t.session) store.set(session.id, { ...t, session })
}

export function forgetThread(sessionId: string) {
  loads.delete(sessionId)
  controllers.get(sessionId)?.abort()
  controllers.delete(sessionId)
  store.set(sessionId, { ...EMPTY, status: 'missing' })
}

let seq = 0
const tempId = () => `pending-${Date.now()}-${seq++}`

/** Local demo output is never submitted to the API or included in a shared session. */
export function postToThread(sessionId: string, message: Pick<ChatMessage, 'content' | 'playground'> & { role: 'tutor' | 'learner' }) {
  const t = store.get(sessionId)
  if (t.status !== 'ready' || !t.session) return
  const local: ChatMessage = { ...message, id: `playground-${seq++}`, via: 'playground', createdAt: new Date().toISOString() }
  store.set(sessionId, { ...t, messages: [...t.messages, local] })
}

/** Keep the Playground recommendation without replacing the real agent's reply with a mock. */
export async function suggestPlayground(offering: Offering, sessionId: string, text: string) {
  const current = store.get(sessionId)
  if (current.status !== 'ready' || current.session?.offeringId !== offering.id) return
  const offer = await generateScene(offering, text, sessionId)
  if (!offer) return
  const latest = store.get(sessionId)
  if (latest.status !== 'ready' || latest.session?.offeringId !== offering.id) return
  if (latest.messages.some((m) => m.playground?.sceneId === offer.sceneId)) return
  postToThread(sessionId, { role: 'tutor', content: 'You can also explore this in the demo Playground.', playground: offer })
}

/**
 * Run one tutor turn: show the learner's part (if any) and a "thinking" bubble at once,
 * then swap in what the API stored. Local demo messages remain separate from that request.
 */
async function turn(
  sessionId: string,
  learnerText: string | null,
  request: (signal: AbortSignal) => Promise<ChatMessage[]>,
  answerFor?: string,
) {
  const t = store.get(sessionId)
  if (t.sending || t.status !== 'ready') return
  // A refresh started before this turn must not overwrite the completed reply later.
  loads.delete(sessionId)
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
    if (controllers.get(sessionId) !== controller) return
    const cur = store.get(sessionId)
    store.set(sessionId, {
      ...cur,
      messages: chronological([...cur.messages.filter((m) => !temp.has(m.id)), ...saved]),
      sending: false,
    })
    return saved
  } catch (e) {
    if (controllers.get(sessionId) !== controller) return
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
    if (controllers.get(sessionId) === controller) controllers.delete(sessionId)
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
