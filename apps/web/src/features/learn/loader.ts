import type { LoaderFunctionArgs } from 'react-router'
import { getSession, getTopic, listConcepts, listMastery, listTopics } from '../../api/learning'
import { listMaterials } from '../../api/library'
import { listQuizItems } from '../../api/review'

/** /learn with no topic: let the learner pick one. */
export async function learnIndexLoader() {
  return { topics: await listTopics() }
}

/** /learn/:topicId: everything the session view needs. */
export async function learnSessionLoader({ params }: LoaderFunctionArgs) {
  const topic = await getTopic(params.topicId ?? '')
  if (!topic) return { topic: null }

  const [allConcepts, mastery, messages, materials, items] = await Promise.all([
    listConcepts(),
    listMastery(),
    getSession(topic.id),
    listMaterials(),
    listQuizItems(topic.id),
  ])
  const estimate = new Map(mastery.map((m) => [m.conceptId, m.estimate]))

  return {
    topic,
    messages,
    concepts: allConcepts
      .filter((c) => topic.conceptIds.includes(c.id))
      .map((c) => ({ ...c, mastery: estimate.get(c.id) ?? 0 })),
    materialTitles: Object.fromEntries(materials.map((m) => [m.id, m.title])),
    // The diagnose step: the first question for this topic, in any format.
    question: items[0] ?? null,
  }
}
