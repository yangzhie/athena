import type { ChatMessage } from '../../../types'

/** The active agent activity is shared by the chat and Playground's narrow thread. */
export function openActivityId(messages: ChatMessage[]): string | null {
  const i = messages.findLastIndex((m) => m.activity)
  if (i < 0) return null
  const a = messages[i].activity!
  const after = messages.slice(i + 1)
  if (a.kind === 'question') {
    return after.some((m) => m.answerFor === a.question.question_id) ? null : a.activity_id
  }
  if (a.kind === 'explanation') return a.activity_id
  return null
}
