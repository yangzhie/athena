/** Lecturer-only: review the clips lecture indexing proposed. See apps/api README. */
import type { ReviewedClip, ReviewedLecture } from '../features/unit/review/types'
import { call } from './client'
import { mediaUrl } from './lectures'

interface LecturerClipDto {
  id: string
  recording_id: string
  topic_id: string
  topic: string
  title: string
  summary: string
  start_s: number
  end_s: number
  status: ReviewedClip['status']
  proposed: { title: string; start_s: number; end_s: number }
  decided: boolean
}

interface LecturerLectureDto {
  id: string
  offering_id: string
  title: string
  week: number | null
  duration_s: number
  status: ReviewedLecture['status']
  clips: LecturerClipDto[]
  has_media: boolean
}

const toLecture = (l: LecturerLectureDto): ReviewedLecture => ({
  id: l.id,
  offeringId: l.offering_id,
  title: l.title,
  week: l.week ?? 0,
  durationS: l.duration_s,
  status: l.status,
  mediaUrl: l.has_media ? mediaUrl(l.offering_id, l.id) : undefined,
  clips: l.clips.map((c) => ({
    id: c.id,
    recordingId: c.recording_id,
    topicId: c.topic_id,
    topic: c.topic,
    title: c.title,
    summary: c.summary,
    startS: c.start_s,
    endS: c.end_s,
    status: c.status,
    original: { title: c.proposed.title, startS: c.proposed.start_s, endS: c.proposed.end_s },
    decided: c.decided,
  })),
})

const base = (o: string) => `/units/${encodeURIComponent(o)}/lectures`
const clipPath = (o: string, lecture: string, clip: string) =>
  `${base(o)}/${encodeURIComponent(lecture)}/clips/${encodeURIComponent(clip)}`

export async function getLecturesForReview(offeringId: string): Promise<ReviewedLecture[]> {
  return (await call<LecturerLectureDto[]>(`${base(offeringId)}/review`)).map(toLecture)
}

export const setClipStatus = (o: string, lecture: string, clip: string, status: ReviewedClip['status']) =>
  call<void>(`${clipPath(o, lecture, clip)}/status`, { method: 'POST', body: JSON.stringify({ status }) })

export const editClip = (o: string, lecture: string, clip: string, e: { title: string; startS: number; endS: number }) =>
  call<void>(clipPath(o, lecture, clip), {
    method: 'PATCH',
    body: JSON.stringify({ title: e.title, start_s: e.startS, end_s: e.endS }),
  })

export const resetClip = (o: string, lecture: string, clip: string) =>
  call<void>(`${clipPath(o, lecture, clip)}/review`, { method: 'DELETE' })

export const approvePendingClips = (o: string, lecture: string) =>
  call<{ approved: number }>(`${base(o)}/${encodeURIComponent(lecture)}/approve-pending`, { method: 'POST' })
