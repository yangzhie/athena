/**
 * A learning session: one chat inside a unit with a goal the student chose,
 * e.g. "k-fold cross-validation". Private to the student. Maps to one agent
 * session (agent/ POST /sessions with this goal) once the tutor is wired up.
 */
export interface LearningSession {
  id: string
  offeringId: string
  /** What the student wants to learn, as they typed it. Sent to the agent as the goal. */
  goal: string
  /** Shown in the sidebar; starts as the goal, the student can rename it. */
  title: string
  createdAt: string
  updatedAt: string
  /**
   * Shared anonymously with the unit's lecturers by the student (AGENTS.md, Privacy rule 6).
   * They can read and reply until the student stops sharing.
   */
  shared: boolean
  sharedAt?: string
}
