import type { AgentActivity, ChatMessage, LearningSession, SourceReference } from '../types'
import { call } from './client'
import { hasPendingOperation, operationCall, recoverPendingOperation } from './operations'

import type { components } from '../../../../packages/shared/api'
type SessionDto = components['schemas']['LearningSessionOut']
type MessageDto = components['schemas']['Message']

const toSession = (s: SessionDto): LearningSession => ({
  id: s.id,
  offeringId: s.offering_id,
  goal: s.goal,
  title: s.title,
  createdAt: s.created_at,
  updatedAt: s.updated_at,
  shared: s.shared,
  sharedAt: s.shared_at ?? undefined,
  lastLecturerReplyAt: s.last_lecturer_reply_at ?? undefined,
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

/** The agent's sources → citations the chat can show (unknown kinds dropped). */
export const toSourceList = (sources: Record<string, unknown>[]) =>
  sources.map(toSource).filter((s): s is SourceReference => s !== null)

const toMessage = (m: MessageDto): ChatMessage => ({
  id: m.id,
  role: m.role,
  content: m.content,
  sources: toSourceList(m.sources ?? []),
  knowledgeOrigin: m.knowledge_origin ?? undefined,
  activity: m.activity && typeof m.activity.activity_id === 'string' && typeof m.activity.kind === 'string' ? m.activity as unknown as AgentActivity : undefined,
  answerFor: m.answer_for ?? undefined,
  createdAt: m.created_at,
})

const base = (offeringId: string) => `/units/${encodeURIComponent(offeringId)}/sessions`

export const hasPendingSession = (offeringId: string) => hasPendingOperation(base(offeringId))

export async function recoverSession(offeringId: string) {
  const r = await recoverPendingOperation<{ session: SessionDto; messages: MessageDto[] }>(base(offeringId), base(offeringId))
  return r ? { session: toSession(r.session), messages: r.messages.map(toMessage) } : undefined
}

export async function listSessions(offeringId: string): Promise<LearningSession[]> {
  await recoverPendingOperation(base(offeringId), base(offeringId))
  return (await call<SessionDto[]>(base(offeringId))).map(toSession)
}

export async function createSession(offeringId: string, goal: string) {
  const r = await operationCall<{ session: SessionDto; messages: MessageDto[] }>(base(offeringId), { goal })
  return { session: toSession(r.session), messages: r.messages.map(toMessage) }
}

export async function getSession(offeringId: string, sessionId: string) {
  await recoverPendingOperation(`${base(offeringId)}/${encodeURIComponent(sessionId)}/messages`, base(offeringId))
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
  const r = await operationCall<MessageDto[]>(`${base(offeringId)}/${encodeURIComponent(sessionId)}/messages`, { text }, signal)
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

/** Share the session anonymously with the unit's lecturers. */
export async function shareSession(offeringId: string, sessionId: string) {
  return toSession(await call<SessionDto>(`${base(offeringId)}/${encodeURIComponent(sessionId)}/share`, { method: 'POST' }))
}

/** Stop sharing; lecturers lose access immediately. */
export async function unshareSession(offeringId: string, sessionId: string) {
  return toSession(await call<SessionDto>(`${base(offeringId)}/${encodeURIComponent(sessionId)}/share`, { method: 'DELETE' }))
}
