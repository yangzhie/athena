import type { LectureRecording } from '../types'
import { lectureRecordings } from '../mocks/lectures'
import { indexedLectures } from './indexedLectures'

/**
 * An offering's lecture recordings with their clips, newest week first.
 * Lectures indexed locally (see ./indexedLectures.ts) replace the offering's mock lectures.
 */
export async function listLectures(offeringId: string): Promise<LectureRecording[]> {
  const indexed = indexedLectures.filter((r) => r.offeringId === offeringId)
  const source = indexed.length > 0 ? indexed : lectureRecordings.filter((r) => r.offeringId === offeringId)
  return [...source].sort((a, b) => b.week - a.week)
}
