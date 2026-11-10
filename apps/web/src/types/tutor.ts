/**
 * A learner-facing activity from the agent (agent/src/athena_agent/learning.py),
 * attached to a tutor message. Never contains answers or grading criteria.
 * Field names stay snake_case: this mirrors the agent's JSON as stored by apps/api.
 */
export interface AgentChoice {
  choice_id: string
  text: string
}

export interface AgentQuestion {
  kind: 'multiple_choice' | 'open_ended'
  question_id: string
  concept_id: string
  prompt: string
  difficulty: string
  choices?: AgentChoice[]
}

interface Base {
  activity_id: string
}

export type AgentActivity =
  | (Base & { kind: 'question'; question: AgentQuestion })
  | (Base & {
      kind: 'explanation'
      text: string
      content?: { summary: string; steps: string[]; worked_example?: string | null } | null
    })
  | (Base & {
      kind: 'feedback'
      text: string
      content?: { outcome: 'correct' | 'partial' | 'incorrect' | 'uncertain'; message: string; next_prompt?: string | null } | null
    })
  | (Base & { kind: 'hint' | 'completion' | 'rich'; text: string })
