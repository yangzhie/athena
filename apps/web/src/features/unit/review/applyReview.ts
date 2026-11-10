import type { LectureClip, LectureRecording } from '../../../types'
import type { ClipDecision } from './reviewStore'

export type ReviewStatus = 'approved' | 'rejected' | 'pending'

export interface ReviewedClip extends LectureClip {
  status: ReviewStatus
  /** The clip as the indexer proposed it, before edits. */
  original: LectureClip
  /** The lecturer has decided on or edited this clip (so it can be undone). */
  decided: boolean
}

/** A clip with the lecturer's decision and edits applied. */
export function reviewClip(clip: LectureClip, decision?: ClipDecision): ReviewedClip {
  const status: ReviewStatus = decision?.status ?? (clip.approved === false ? 'pending' : 'approved')
  return {
    ...clip,
    title: decision?.title ?? clip.title,
    startS: decision?.startS ?? clip.startS,
    endS: decision?.endS ?? clip.endS,
    approved: status === 'approved',
    status,
    original: clip,
    decided: decision !== undefined,
  }
}

/** What students see: only approved clips, with edits applied, in time order. */
export function studentView(lecture: LectureRecording, decisions: Record<string, ClipDecision>): LectureRecording {
  const clips = lecture.clips
    .map((c) => reviewClip(c, decisions[c.id]))
    .filter((c) => c.status === 'approved')
    .sort((a, b) => a.startS - b.startS)
  const pending = lecture.clips.some((c) => reviewClip(c, decisions[c.id]).status === 'pending')
  return { ...lecture, clips, draft: pending }
}
