export type QuizFormat = 'mcq' | 'numeric' | 'short'
export type BloomLevel = 'recall' | 'apply' | 'analyse'

export interface QuizItem {
  id: string
  topicId: string
  conceptIds: string[]
  format: QuizFormat
  stem: string
  /** Multiple-choice options; only for format "mcq". */
  options?: string[]
  /** Option index for mcq, number for numeric, rubric text for short. */
  answer: number | string
  /** 1 (easiest) to 5. */
  difficulty: 1 | 2 | 3 | 4 | 5
  bloom: BloomLevel
}

/** Per-learner spaced repetition state for one item (FSRS). */
export interface ReviewState {
  itemId: string
  dueAt: string
  stability: number
  difficulty: number
}
