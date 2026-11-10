import type { AgentActivity, ChatMessage, KnowledgeOrigin, LearningSession, SourceReference } from '../types'
import { call } from './client'

/** Session as the API returns it (snake_case). */
interface SessionDto {
  id: string
  offering_id: string
  goal: string
  title: string
  created_at: string
  updated_at: string
  shared: boolean
}

interface MessageDto {
  id: string
  role: 'tutor' | 'learner'
  content: string
  sources: Record<string, unknown>[]
  knowledge_origin: KnowledgeOrigin | null
  activity: AgentActivity | null
  answer_for: string | null
  created_at: string
}

const toSession = (s: SessionDto): LearningSession => ({
  id: s.id,
  offeringId: s.offering_id,
  goal: s.goal,
  title: s.title,
  createdAt: s.created_at,
  updatedAt: s.updated_at,
  shared: s.shared,
})

/** The agent's SourceReference (snake_case) → the app's camelCase type. Unknown kinds are dropped. */
function toSource(s: Record<string, unknown>): SourceReference | null {
  if (s.kind === 'document') {
    return {
      kind: 'document',
      sourceId: String(s.source_id),
      passageId: String(s.passage_id),
      title: String(s.title),
      quote: String(s.quote),
      page: typeof s.page === 'number' ? s.page : undefined,
      section: typeof s.section === 'string' ? s.section : undefined,
    }
  }
  if (s.kind === 'video') {
    return {
      kind: 'video',
      sourceId: String(s.source_id),
      segmentId: String(s.segment_id),
      title: String(s.title),
      quote: String(s.quote),
      startS: Number(s.start_seconds),
      endS: Number(s.end_seconds),
    }
  }
  return null
}

const toMessage = (m: MessageDto): ChatMessage => ({
  id: m.id,
  role: m.role,
  content: m.content,
  sources: m.sources.map(toSource).filter((s): s is SourceReference => s !== null),
  knowledgeOrigin: m.knowledge_origin ?? undefined,
  activity: m.activity ?? undefined,
  answerFor: m.answer_for ?? undefined,
  createdAt: m.created_at,
})

const base = (offeringId: string) => `/units/${encodeURIComponent(offeringId)}/sessions`

export async function listSessions(offeringId: string): Promise<LearningSession[]> {
  return (await call<SessionDto[]>(base(offeringId))).map(toSession)
}

export async function createSession(offeringId: string, goal: string) {
  const r = await call<{ session: SessionDto; messages: MessageDto[] }>(base(offeringId), {
    method: 'POST',
    body: JSON.stringify({ goal }),
  })
  return { session: toSession(r.session), messages: r.messages.map(toMessage) }
}

export async function getSession(offeringId: string, sessionId: string) {
  const r = await call<{ session: SessionDto; messages: MessageDto[] }>(`${base(offeringId)}/${encodeURIComponent(sessionId)}`)
  return { session: toSession(r.session), messages: r.messages.map(toMessage) }
}

export async function renameSession(offeringId: string, sessionId: string, title: string) {
  return toSession(
    await call<SessionDto>(`${base(offeringId)}/${encodeURIComponent(sessionId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),
  )
}

export async function deleteSession(offeringId: string, sessionId: string) {
  await call<void>(`${base(offeringId)}/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
}

/** Sends the learner's message; returns [learner message, tutor reply] as stored. */
export async function sendSessionMessage(offeringId: string, sessionId: string, text: string, signal?: AbortSignal) {
  const r = await call<MessageDto[]>(`${base(offeringId)}/${encodeURIComponent(sessionId)}/messages`, {
    method: 'POST',
    body: JSON.stringify({ text }),
    signal,
  })
  return r.map(toMessage)
}

export interface AnswerInput {
  questionId: string
  /** Multiple choice: the chosen option's id. */
  choiceId?: string
  /** Open-ended: the learner's answer. */
  text?: string
  /** How the answer appears in the chat (the option's text, or the typed answer). */
  shown: string
}

/** Answers the tutor's question; returns [learner answer, tutor's next messages…]. */
export async function answerQuestion(offeringId: string, sessionId: string, a: AnswerInput, signal?: AbortSignal) {
  const r = await call<MessageDto[]>(`${base(offeringId)}/${encodeURIComponent(sessionId)}/answers`, {
    method: 'POST',
    body: JSON.stringify({ question_id: a.questionId, choice_id: a.choiceId ?? null, text: a.text ?? null, shown: a.shown }),
    signal,
  })
  return r.map(toMessage)
}

/** Moves on after a teaching step; returns the tutor's next messages. */
export async function continueSession(offeringId: string, sessionId: string, activityId: string, signal?: AbortSignal) {
  const r = await call<MessageDto[]>(`${base(offeringId)}/${encodeURIComponent(sessionId)}/continue`, {
    method: 'POST',
    body: JSON.stringify({ activity_id: activityId }),
    signal,
  })
  return r.map(toMessage)
}
