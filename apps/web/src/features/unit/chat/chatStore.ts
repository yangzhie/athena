import { useSyncExternalStore } from 'react'
import { streamTutorReply } from '../../../api/tutor'
import { readStored, writeStored } from '../../../lib/storage'
import type { ChatMessage, Offering } from '../../../types'

/**
 * One chat thread per learning session. Saved in this browser after each
 * finished reply (not on every streamed word); moves to apps/api later.
 */
export interface Thread {
  messages: ChatMessage[]
  streaming: boolean
}

const KEY = 'athena.threads'
const EMPTY: Thread = { messages: [], streaming: false }
const threads = new Map<string, Thread>(load())
const controllers = new Map<string, AbortController>()
const listeners = new Set<() => void>()

function load(): [string, Thread][] {
  try {
    const saved = JSON.parse(readStored(KEY) ?? '{}') as Record<string, ChatMessage[]>
    return Object.entries(saved).map(([id, messages]) => [id, { messages, streaming: false }])
  } catch {
    return []
  }
}

function save() {
  const out: Record<string, ChatMessage[]> = {}
  for (const [id, t] of threads) out[id] = t.messages
  writeStored(KEY, JSON.stringify(out))
}

function set(id: string, update: (t: Thread) => Thread) {
  threads.set(id, update(threads.get(id) ?? EMPTY))
  listeners.forEach((l) => l())
}

/** Start a thread with a first message (the tutor's opening). */
export function seedThread(sessionId: string, message: ChatMessage) {
  set(sessionId, () => ({ messages: [message], streaming: false }))
  save()
}

export function deleteThread(sessionId: string) {
  controllers.get(sessionId)?.abort()
  threads.delete(sessionId)
  listeners.forEach((l) => l())
  save()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useThread(sessionId: string): Thread {
  return useSyncExternalStore(subscribe, () => threads.get(sessionId) ?? EMPTY)
}

let seq = 0
const newId = () => `msg-${Date.now()}-${seq++}`

export async function sendMessage(offering: Offering, sessionId: string, text: string) {
  const id = sessionId
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
    if (threads.has(id)) {
      set(id, (t) => ({ ...t, streaming: false }))
      save()
    }
  }
}

export function stopStreaming(sessionId: string) {
  controllers.get(sessionId)?.abort()
}
