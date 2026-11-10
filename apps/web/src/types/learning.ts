import type { KnowledgeOrigin, SourceReference } from './sources'
import type { PlaygroundOffer } from './playground'
import type { AgentActivity } from './tutor'

/** A global idea that topics map to, e.g. "subnetting" or "overfitting". */
export interface Concept {
  id: string
  name: string
  /** Concepts that should be understood first. */
  prerequisiteIds: string[]
}

/**
 * Something the learner chose to study. "small" topics run one short loop
 * (e.g. bubble sort); "broad" topics run many loops across concepts (e.g. ML).
 */
export interface Topic {
  id: string
  title: string
  description: string
  scope: 'small' | 'broad'
  conceptIds: string[]
  /** Uploaded materials this topic is grounded in, if any. */
  materialIds: string[]
  lastStudiedAt?: string
}

/** Estimate of how well the learner understands one concept. */
export interface Mastery {
  conceptId: string
  /** 0 to 1. */
  estimate: number
  /** 0 to 1; high means we have little evidence yet. */
  uncertainty: number
  evidenceCount: number
  updatedAt: string
}

export interface ChatMessage {
  id: string
  /** lecturer = a reply from the unit's lecturer in a session the student shared. */
  role: 'tutor' | 'learner' | 'lecturer'
  content: string
  /** Material the reply is based on. Tutor messages only. */
  sources?: SourceReference[]
  knowledgeOrigin?: KnowledgeOrigin
  /** A demo Playground offered for this learning session. */
  playground?: PlaygroundOffer
  /** Local demo message: never sent to the API, saved or shared with a lecturer. */
  via?: 'playground'
  /** Tutor messages from the agent: the question, explanation, feedback, ... behind it. */
  activity?: AgentActivity
  /** Learner messages that answer a question: that question's id. */
  answerFor?: string
  createdAt: string
}
