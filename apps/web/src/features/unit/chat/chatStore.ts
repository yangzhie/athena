import { useSyncExternalStore } from 'react'
import { streamTutorReply } from '../../../api/tutor'
import type { ChatMessage, Offering } from '../../../types'

/**
 * One chat thread per offering, kept in memory so switching units in the
 * sidebar doesn't lose the conversation. Not persisted across reloads yet.
 */
export interface Thread {
  messages: ChatMessage[]
  streaming: boolean
}

const EMPTY: Thread = { messages: [], streaming: false }
const threads = new Map<string, Thread>()
const controllers = new Map<string, AbortController>()
const listeners = new Set<() => void>()

function set(id: string, update: (t: Thread) => Thread) {
  threads.set(id, update(threads.get(id) ?? EMPTY))
  listeners.forEach((l) => l())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useThread(offeringId: string): Thread {
  return useSyncExternalStore(subscribe, () => threads.get(offeringId) ?? EMPTY)
}

let seq = 0
const newId = () => `msg-${Date.now()}-${seq++}`

export async function sendMessage(offering: Offering, text: string) {
  const id = offering.id
  if (threads.get(id)?.streaming) return

  const learner: ChatMessage = { id: newId(), role: 'learner', content: text, createdAt: new Date().toISOString() }
  const tutor: ChatMessage = { id: newId(), role: 'tutor', content: '', createdAt: new Date().toISOString() }
  set(id, (t) => ({ messages: [...t.messages, learner, tutor], streaming: true }))

  const controller = new AbortController()
  controllers.set(id, controller)
  const history = threads.get(id)!.messages.slice(0, -1)

  try {
    for await (const event of streamTutorReply(offering, history, controller.signal)) {
      set(id, (t) => ({
        ...t,
        messages: t.messages.map((m) => {
          if (m.id !== tutor.id) return m
          return event.type === 'text'
            ? { ...m, content: m.content + event.text }
            : { ...m, sources: event.sources, knowledgeOrigin: event.knowledgeOrigin }
        }),
      }))
    }
  } catch {
    set(id, (t) => ({
      ...t,
      messages: t.messages.map((m) =>
        m.id === tutor.id ? { ...m, content: m.content + '\n\nSomething went wrong. Try again.' } : m,
      ),
    }))
  } finally {
    controllers.delete(id)
    set(id, (t) => ({ ...t, streaming: false }))
  }
}

export function stopStreaming(offeringId: string) {
  controllers.get(offeringId)?.abort()
}
