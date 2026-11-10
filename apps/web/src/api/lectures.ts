import type { LectureClip, LectureRecording } from '../types'
import { call } from './client'

/** A lecture as the API gives students: approved clips only, no transcripts. */
interface StudentLectureDto {
  id: string
  offering_id: string
  title: string
  week: number | null
  duration_s: number
  status: LectureRecording['status']
  under_review: boolean
  has_media: boolean
  clips: { id: string; recording_id: string; topic_id: string; topic: string; title: string; summary: string; start_s: number; end_s: number }[]
}

export function toClip(c: StudentLectureDto['clips'][number]): LectureClip {
  return {
    id: c.id,
    recordingId: c.recording_id,
    topicId: c.topic_id,
    topic: c.topic,
    title: c.title,
    summary: c.summary,
    startS: c.start_s,
    endS: c.end_s,
  }
}

/** The API streams the recording (with seeking) to signed-in students and lecturers. */
export const mediaUrl = (offeringId: string, lectureId: string) =>
  `/api/units/${encodeURIComponent(offeringId)}/lectures/${encodeURIComponent(lectureId)}/media`

const toLecture = (l: StudentLectureDto): LectureRecording => ({
  id: l.id,
  offeringId: l.offering_id,
  title: l.title,
  week: l.week ?? 0,
  durationS: l.duration_s,
  status: l.status,
  draft: l.under_review,
  mediaUrl: l.has_media ? mediaUrl(l.offering_id, l.id) : undefined,
  clips: l.clips.map(toClip),
})

/** An Offering's approved clips; unavailable/empty responses never select fixtures. */
export async function listLectures(offeringId: string): Promise<LectureRecording[]> {
  const lectures = (await call<StudentLectureDto[]>(`/units/${encodeURIComponent(offeringId)}/lectures`)).map(toLecture)
  return lectures.sort((a, b) => b.week - a.week)
}
