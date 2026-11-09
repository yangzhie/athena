import type { LectureRecording } from '../types'
import { lectureRecordings } from '../mocks/lectures'

/** An offering's lecture recordings with their approved clips, newest week first. */
export async function listLectures(offeringId: string): Promise<LectureRecording[]> {
  return lectureRecordings.filter((r) => r.offeringId === offeringId).sort((a, b) => b.week - a.week)
}
