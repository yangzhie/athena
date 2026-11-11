import { useEffect, useState } from 'react'
import { listLectures } from '../../../api/lectures'
import { listCourseTopics } from '../../../api/progress'

/**
 * A unit-specific example goal for the "What do you want to learn?" box, drawn
 * from the unit's own topics and its approved lecture clip titles (which lecture
 * indexing produced and the lecturer approved). Clip titles are more specific,
 * so they're preferred when there are any.
 */
export function pickGoalExample(topics: string[], clipTitles: string[], random: () => number = Math.random): string | null {
  const clean = (list: string[]) => [...new Set(list.map((s) => s.trim()).filter((s) => s.length >= 3 && s.length <= 70))]
  const pool = clean(clipTitles).length > 0 ? clean(clipTitles) : clean(topics)
  if (pool.length === 0) return null
  return pool[Math.floor(random() * pool.length) % pool.length]
}

/** The placeholder text for a unit: "e.g. <example>", or a generic hint while loading or if the unit has nothing yet. */
export function useGoalPlaceholder(offeringId: string, unitTitle: string): string {
  const [example, setExample] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      listCourseTopics(offeringId).catch(() => []),
      listLectures(offeringId).catch(() => []),
    ]).then(([topics, lectures]) => {
      if (cancelled) return
      const clipTitles = lectures.filter((l) => l.offeringId === offeringId).flatMap((l) => l.clips.map((c) => c.title))
      setExample(pickGoalExample(topics.map((t) => t.title), clipTitles))
    })
    return () => {
      cancelled = true
    }
  }, [offeringId])

  return example ? `e.g. ${example}` : `e.g. a topic from ${unitTitle}`
}
