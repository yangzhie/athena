export type RecordingStatus = 'processing' | 'ready' | 'failed'

/** An uploaded lecture recording in an offering. */
export interface LectureRecording {
  id: string
  offeringId: string
  title: string
  week: number
  durationS: number
  status: RecordingStatus
  /** Empty while processing. */
  clips: LectureClip[]
  /** True when clips came from lecture indexing and the lecturer hasn't approved them yet. */
  draft?: boolean
}

/**
 * A topic-labelled time range over one recording, produced by lecture indexing
 * and approved by the lecturer. Played as offsets into the recording's stream,
 * not a separate file.
 */
export interface LectureClip {
  id: string
  recordingId: string
  title: string
  topic: string
  summary: string
  startS: number
  endS: number
}
