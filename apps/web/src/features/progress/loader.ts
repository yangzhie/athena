import { listConcepts, listMastery, listTopics } from '../../api/learning'
import { MASTERED, masteryLevel } from '../../lib/mastery'

export async function progressLoader() {
  const [concepts, mastery, topics] = await Promise.all([listConcepts(), listMastery(), listTopics()])
  const estimate = new Map(mastery.map((m) => [m.conceptId, m.estimate]))
  const name = new Map(concepts.map((c) => [c.id, c.name]))
  const score = (id: string) => estimate.get(id) ?? 0

  const counts = { mastered: 0, learning: 0, gap: 0 }
  for (const c of concepts) counts[masteryLevel(score(c.id))]++

  // Mastery-driven ordering: a concept is ready once all its prerequisites are mastered.
  const unmastered = concepts.filter((c) => score(c.id) < MASTERED)
  const ready = unmastered
    .filter((c) => c.prerequisiteIds.every((p) => score(p) >= MASTERED))
    .map((c) => ({ id: c.id, name: c.name, mastery: score(c.id) }))
    .sort((a, b) => b.mastery - a.mastery)
  const blocked = unmastered
    .filter((c) => !c.prerequisiteIds.every((p) => score(p) >= MASTERED))
    .map((c) => ({
      id: c.id,
      name: c.name,
      blockedBy: c.prerequisiteIds.filter((p) => score(p) < MASTERED).map((p) => name.get(p) ?? p),
    }))

  return {
    total: concepts.length,
    counts,
    ready,
    blocked,
    topics: topics.map((t) => ({
      id: t.id,
      title: t.title,
      concepts: t.conceptIds.map((id) => ({ id, name: name.get(id) ?? id, mastery: score(id) })),
    })),
  }
}
