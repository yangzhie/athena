import type { Offering } from '../types'
import { ApiError, call } from './client'

/** Published Offerings, plus drafts this anonymous browser can manage. */
export function listEnrolledOfferings(): Promise<Offering[]> {
  return call('/offerings')
}

export async function getEnrolledOffering(id: string): Promise<Offering | undefined> {
  try { return await call(`/offerings/${encodeURIComponent(id)}`) }
  catch (error) {
    if (error instanceof ApiError && error.status === 404) return undefined
    throw error
  }
}

export function createStudySpace(input: { code: string; title: string; year: number; semester: string }): Promise<Offering> {
  return call('/offerings', { method: 'POST', body: JSON.stringify(input) })
}

export function publishStudySpace(id: string): Promise<Offering> {
  return call(`/offerings/${encodeURIComponent(id)}/publish`, { method: 'POST' })
}
