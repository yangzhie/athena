import type { ChatMessage } from '../../../types'

export type LessonStage = 'diagnose' | 'teach' | 'check' | 'done'

export const STAGES: { id: LessonStage; label: string }[] = [
  { id: 'diagnose', label: 'Diagnose' },
  { id: 'teach', label: 'Teach' },
  { id: 'check', label: 'Check' },
  { id: 'done', label: 'Done' },
]

export interface LessonProgress {
  stage: LessonStage
  /** Question number (1-based) for each question activity id. */
  questionNumber: Record<string, number>
  asked: number
  answered: number
  correct: number
}

/**
 * Where the session is in the adaptive loop, worked out from the activities the
 * student has already seen (the API doesn't expose the agent's phase).
 * Questions before any teaching are diagnosis; questions after teaching are checks.
 */
export function lessonProgress(messages: ChatMessage[]): LessonProgress {
  let stage: LessonStage = 'diagnose'
  let taught = false
  const questionNumber: Record<string, number> = {}
  let asked = 0, answered = 0, correct = 0
  for (const m of messages) {
    const a = m.activity
    if (m.role !== 'tutor' || !a) continue
    if (a.kind === 'question') {
      questionNumber[a.activity_id] = ++asked
      stage = taught ? 'check' : 'diagnose'
    } else if (a.kind === 'explanation') {
      taught = true
      stage = 'teach'
    } else if (a.kind === 'feedback' && a.content) {
      answered++
      if (a.content.outcome === 'correct') correct++
    } else if (a.kind === 'completion') {
      stage = 'done'
    }
  }
  return { stage, questionNumber, asked, answered, correct }
}
