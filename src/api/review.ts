import type { QuizItem } from '../types'
import { quizItems, reviewStates } from '../mocks/data'

export async function listQuizItems(topicId?: string): Promise<QuizItem[]> {
  return topicId ? quizItems.filter((q) => q.topicId === topicId) : quizItems
}

/** Items whose review is due at or before `now`. */
export async function listDueItems(now = new Date()): Promise<QuizItem[]> {
  const due = new Set(reviewStates.filter((r) => new Date(r.dueAt) <= now).map((r) => r.itemId))
  return quizItems.filter((q) => due.has(q.id))
}
