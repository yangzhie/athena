import type { Concept, Mastery, Topic } from '../types'
import { getLearnerProfile, getProgress, listCourseTopics } from './progress'

export async function listTopics(offeringId?: string): Promise<Topic[]> {
  if (!offeringId) return []
  return (await listCourseTopics(offeringId)).map(topic => ({ id: topic.id, title: topic.title, description: '', scope: 'small', conceptIds: [topic.concept_id], materialIds: [] }))
}
export async function getTopic(id: string, offeringId?: string): Promise<Topic | undefined> {
  return (await listTopics(offeringId)).find(topic => topic.id === id)
}
export async function listConcepts(): Promise<Concept[]> {
  return (await getLearnerProfile()).map(concept => ({ id: concept.id, name: concept.name, prerequisiteIds: [] }))
}
export async function listMastery(offeringId?: string): Promise<Mastery[]> {
  const profile = offeringId ? await getProgress(offeringId) : await getLearnerProfile()
  return profile.map(item => ({ conceptId: item.id, status: item.status,
    estimate: item.status === 'mastered' ? 1 : item.status === 'developing' ? .5 : 0,
    uncertainty: item.status === 'unknown' ? 1 : .5, evidenceCount: item.evidence_count,
    updatedAt: new Date(item.updated_at * 1000).toISOString() }))
}
