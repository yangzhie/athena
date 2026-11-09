import type { ChatMessage, Concept, Mastery, Topic } from '../types'
import { concepts, mastery, sampleSession, topics } from '../mocks/data'

// Mock implementations. Swap the bodies for fetch() calls when the API exists;
// the signatures are what pages depend on, so keep them stable.

export async function listTopics(): Promise<Topic[]> {
  return topics
}

export async function getTopic(id: string): Promise<Topic | undefined> {
  return topics.find((t) => t.id === id)
}

export async function listConcepts(): Promise<Concept[]> {
  return concepts
}

export async function listMastery(): Promise<Mastery[]> {
  return mastery
}

/** The mock only has a conversation for the ML topic. */
export async function getSession(topicId: string): Promise<ChatMessage[]> {
  return topicId === 'machine-learning' ? sampleSession : []
}
