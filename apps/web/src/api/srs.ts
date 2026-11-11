/**
 * Spaced repetition, served by apps/api (FastAPI). The first frontend feature
 * that talks to a real backend: in dev, Vite proxies /api to it.
 * Answers are graded on the server; questions never include their answers.
 */

import { operationCall, recoverPracticeOperations } from './operations'
import { call } from './client'

export { ApiError } from './client'

export type Rating = 'again' | 'hard' | 'good' | 'easy'

export interface SrsQuestion {
  variant_id: string
  kind: 'mcq' | 'numeric' | 'short'
  stem: string
  options?: string[]
}

export type SrsNext =
  | {
      done: false
      item_id: string
      topic_id: string
      is_new: boolean
      question: SrsQuestion
      remaining: { due: number; new: number }
      restored_attempt?: SrsAttemptResult
    }
  | { done: true; next_due_at: string | null }

export interface SrsFeedback {
  explanation: string
  clip_ids: string[]
  correct_option?: number
  correct_value?: number
  model_answer?: string
  rubric?: string[]
}

export interface SrsAttemptResult {
  attempt_id: string
  /** null for short answers: the student rates themselves. */
  correct: boolean | null
  feedback: SrsFeedback
  needs_rating: boolean
  rating_options?: Rating[]
  next_due_at?: string
}

export interface SrsSummary {
  total_items: number
  due_now: number
  new_available: number
  reviewed_today: number
  next_due_at: string | null
}

const base = (offeringId: string) => `/units/${encodeURIComponent(offeringId)}/srs`

export async function getSrsSummary(offeringId: string) {
  await recoverPracticeOperations(base(offeringId))
  return call<SrsSummary>(`${base(offeringId)}/summary`)
}

export async function getNextQuestion(offeringId: string): Promise<SrsNext> {
  await recoverPracticeOperations(base(offeringId))
  const pending = await call<SrsNext | null>(`${base(offeringId)}/pending`)
  return pending ?? call<SrsNext>(`${base(offeringId)}/next`)
}

export const submitAnswer = (offeringId: string, itemId: string, variantId: string, answer: number | string | null) =>
  operationCall<SrsAttemptResult>(`${base(offeringId)}/attempts`, { item_id: itemId, variant_id: variantId, answer })

export const rateAttempt = (offeringId: string, attemptId: string, rating: Rating) =>
  operationCall<{ next_due_at: string }>(`${base(offeringId)}/attempts/${encodeURIComponent(attemptId)}/rating`, { rating })
