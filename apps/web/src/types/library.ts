export type MaterialKind = 'pdf' | 'slides' | 'doc' | 'recording'
export type MaterialStatus = 'processing' | 'ready' | 'failed'

/** A file the learner uploaded: textbook, slides, notes or a lecture recording. */
export interface Material {
  id: string
  title: string
  kind: MaterialKind
  status: MaterialStatus
  uploadedAt: string
  topicIds: string[]
}

/** A topic-labelled time range in a recording. Not a separate file. */
export interface LectureClip {
  id: string
  materialId: string
  topicId: string
  title: string
  summary: string
  startS: number
  endS: number
}
