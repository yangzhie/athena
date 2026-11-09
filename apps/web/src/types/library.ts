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
