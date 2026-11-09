/**
 * Where a tutor answer came from. Mirrors the agent's SourceReference /
 * knowledge_origin (agent/src/athena_agent/retrieval.py), in camelCase.
 */
export type SourceReference = DocumentReference | VideoReference

export interface DocumentReference {
  kind: 'document'
  sourceId: string
  passageId: string
  /** Document title, e.g. "Week 3 slides: Model evaluation". */
  title: string
  /** The passage the answer relies on. */
  quote: string
  page?: number
  section?: string
}

export interface VideoReference {
  kind: 'video'
  /** Recording id. */
  sourceId: string
  /** Clip id within the recording. */
  segmentId: string
  title: string
  quote: string
  startS: number
  endS: number
}

/**
 * materials: answered from the unit's material.
 * supplement: material plus clearly labelled general knowledge.
 * general: not covered by the material; general knowledge only.
 */
export type KnowledgeOrigin = 'materials' | 'supplement' | 'general'
