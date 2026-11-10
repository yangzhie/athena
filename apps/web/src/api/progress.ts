import { call } from './client'

export interface ConceptProgress {
  id: string
  name: string
  status: 'unknown' | 'developing' | 'mastered'
  note: string
  evidence_count: number
  updated_at: number
  next_action: string
}
export interface OfferingInsights {
  sufficient_data: boolean
  minimum_environments?: number
  sample_data: boolean
  contributing_environments?: number
  sessions?: number
  completed_sessions?: number
  practice_reviews?: number
  population_label?: string
  concepts: { id: string; name: string; assessments: number; environments: number; difficulty_rate: number }[]
  gaps: { category: string; environments: number }[]
}
export interface CourseTopic { id: string; title: string; concept_id: string }
const unit = (id: string) => `/units/${encodeURIComponent(id)}`
export const getProgress = (offering: string): Promise<ConceptProgress[]> => call(`${unit(offering)}/progress`)
export const getLearnerProfile = (): Promise<ConceptProgress[]> => call('/learner/profile')
export const getInsights = (offering: string): Promise<OfferingInsights> => call(`${unit(offering)}/insights`)
export const listCourseTopics = (offering: string): Promise<CourseTopic[]> => call(`${unit(offering)}/topics`)
export const conceptCatalogue = (): Promise<{ id: string; name: string }[]> => call('/concepts/catalogue')
export const addCourseTopic = (offering: string, title: string, concept_id?: string): Promise<CourseTopic> => call(`${unit(offering)}/topics`, { method: 'POST', body: JSON.stringify({ title, concept_id }) })
