/** Lecturer-only: sessions students have shared, anonymously (AGENTS.md, Privacy rule 6). */
import type { AgentActivity, ChatMessage, KnowledgeOrigin } from '../types'
import { call } from './client'
import { toSourceList } from './sessions'

export interface SharedSessionSummary {
  shareId: string
  studentLabel: string
  title: string
  goal: string
  sharedAt: string
  updatedAt: string
  messageCount: number
}

interface SummaryDto {
  share_id: string
  student_label: string
  title: string
  goal: string
  shared_at: string
  updated_at: string
  message_count: number
}

interface MessageDto {
  id: string
  role: 'tutor' | 'learner' | 'lecturer'
  content: string
  sources: Record<string, unknown>[]
  knowledge_origin: KnowledgeOrigin | null
  activity: AgentActivity | null
  answer_for: string | null
  created_at: string
}

const toSummary = (s: SummaryDto): SharedSessionSummary => ({
  shareId: s.share_id,
  studentLabel: s.student_label,
  title: s.title,
  goal: s.goal,
  sharedAt: s.shared_at,
  updatedAt: s.updated_at,
  messageCount: s.message_count,
})

const base = (o: string) => `/units/${encodeURIComponent(o)}/shared-sessions`

export async function listSharedSessions(offeringId: string) {
  return (await call<SummaryDto[]>(base(offeringId))).map(toSummary)
}

export async function getSharedSession(offeringId: string, shareId: string) {
  const r = await call<{ session: SummaryDto; messages: MessageDto[] }>(`${base(offeringId)}/${encodeURIComponent(shareId)}`)
  return {
    session: toSummary(r.session),
    messages: r.messages.map(
      (m): ChatMessage => ({
        id: m.id,
        role: m.role,
        content: m.content,
        sources: toSourceList(m.sources),
        knowledgeOrigin: m.knowledge_origin ?? undefined,
        activity: m.activity ?? undefined,
        answerFor: m.answer_for ?? undefined,
        createdAt: m.created_at,
      }),
    ),
  }
}
