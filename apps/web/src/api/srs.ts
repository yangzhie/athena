/**
 * Spaced repetition, served by apps/api (FastAPI). The first frontend feature
 * that talks to a real backend: in dev, Vite proxies /api to it.
 * Answers are graded on the server; questions never include their answers.
 */

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

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'The Athena API isn’t reachable.')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    // The Vite proxy answers 5xx with no JSON body when the API isn't running.
    if (res.status >= 500 && !body) throw new ApiError(0, 'The Athena API isn’t reachable.')
    throw new ApiError(res.status, body?.detail ?? `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

const base = (offeringId: string) => `/units/${encodeURIComponent(offeringId)}/srs`

export const getSrsSummary = (offeringId: string) => call<SrsSummary>(`${base(offeringId)}/summary`)

export const getNextQuestion = (offeringId: string) => call<SrsNext>(`${base(offeringId)}/next`)

export const submitAnswer = (offeringId: string, itemId: string, variantId: string, answer: number | string | null) =>
  call<SrsAttemptResult>(`${base(offeringId)}/attempts`, {
    method: 'POST',
    body: JSON.stringify({ item_id: itemId, variant_id: variantId, answer }),
  })

export const rateAttempt = (offeringId: string, attemptId: string, rating: Rating) =>
  call<{ next_due_at: string }>(`${base(offeringId)}/attempts/${encodeURIComponent(attemptId)}/rating`, {
    method: 'POST',
    body: JSON.stringify({ rating }),
  })
