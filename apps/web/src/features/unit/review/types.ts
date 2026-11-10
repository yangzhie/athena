import type { LectureClip, LectureRecording } from '../../../types'

export type ReviewStatus = 'approved' | 'rejected' | 'pending'

/** A clip as the lecturer reviews it: current values plus what the indexer proposed. */
export interface ReviewedClip extends LectureClip {
  status: ReviewStatus
  original: Pick<LectureClip, 'title' | 'startS' | 'endS'>
  /** The lecturer has decided on or edited this clip (so it can be undone). */
  decided: boolean
}

export interface ReviewedLecture extends Omit<LectureRecording, 'clips' | 'draft'> {
  clips: ReviewedClip[]
}
