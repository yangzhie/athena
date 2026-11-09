import { listMastery, listTopics } from '../../api/learning'

export async function homeLoader() {
  const [topics, mastery] = await Promise.all([listTopics(), listMastery()])
  const byConcept = new Map(mastery.map((m) => [m.conceptId, m.estimate]))

  return {
    topics: topics.map((topic) => {
      // Concepts with no evidence yet count as 0.
      const scores = topic.conceptIds.map((id) => byConcept.get(id) ?? 0)
      const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0
      return { ...topic, mastery: avg }
    }),
  }
}
