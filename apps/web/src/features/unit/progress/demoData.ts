import type { OfferingInsights } from '../../../api/progress'

/**
 * Hard-coded sample data for the three demo units (docs/demo-units.md), so Insights shows
 * something in any browser. Invented numbers, always labelled "Sample data".
 * Per topic: [name, the class's share of assessments needing more work].
 */
const DEMO: Record<string, { environments: number; sessions: number; completed: number; practice: number; topics: [string, number][] }> = {
  CHEM1001: { environments: 26, sessions: 55, completed: 28, practice: 91, topics: [
    ['Oxidation states', 0.18],
    ['Balancing redox reactions', 0.47],
    ['Galvanic cells', 0.39],
    ['Standard reduction potentials', 0.55],
    ['Electrolytic cells', 0.33],
  ] },
  PHYS1001: { environments: 31, sessions: 68, completed: 37, practice: 104, topics: [
    ["Newton's first law and inertia", 0.21],
    ["Newton's second law", 0.36],
    ["Newton's third law", 0.52],
    ['Mass and weight', 0.28],
    ['Free-body diagrams', 0.44],
  ] },
  COMP1001: { environments: 22, sessions: 45, completed: 26, practice: 77, topics: [
    ['What is computation', 0.12],
    ['Python objects and types', 0.31],
    ['Expressions and operators', 0.38],
    ['Variables and binding', 0.49],
    ['Strings and input/output', 0.27],
  ] },
}

/** 95% Wilson score interval for a proportion (matches the API's `wilson`). */
export function wilson(successes: number, n: number, z = 1.96): [number, number] {
  const p = successes / n
  const centre = (p + (z * z) / (2 * n)) / (1 + (z * z) / n)
  const half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / (1 + (z * z) / n)
  return [Math.max(0, centre - half), Math.min(1, centre + half)]
}

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-')

export function demoInsights(unitCode: string): OfferingInsights | null {
  const unit = DEMO[unitCode]
  if (!unit) return null
  return {
    sufficient_data: true, sample_data: true, contributing_environments: unit.environments, sessions: unit.sessions,
    completed_sessions: unit.completed, practice_reviews: unit.practice,
    population_label: 'Sample data: an invented cohort of anonymous learning Environments.',
    concepts: unit.topics.map(([name, difficulty], i) => {
      const assessments = 50 + ((i * 17 + unit.environments) % 40)
      const [ci_low, ci_high] = wilson(Math.round(difficulty * assessments), assessments)
      return { id: `sample-${slug(name)}`, name, assessments, environments: Math.round(unit.environments * 0.75), difficulty_rate: difficulty, ci_low, ci_high }
    }),
    gaps: [
      { category: 'needs_practice', environments: Math.round(unit.environments * 0.6) },
      { category: 'prerequisite_gap', environments: Math.round(unit.environments * 0.35) },
      { category: 'needs_independent_reasoning', environments: Math.round(unit.environments * 0.3) },
    ],
  }
}

export interface DemoStudent {
  /** Pseudonym only: opted-in individual insight never shows identity. */
  label: string
  lastActive: string
  sessions: number
  overall: { accuracy: number; ci_low: number; ci_high: number; assessed: number }
  topics: { name: string; assessed: number; accuracy: number | null; ci_low: number | null; ci_high: number | null }[]
}

/** Small seeded generator so the fake students are the same on every load. */
function seeded(seed: string) {
  let h = 2166136261
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 16777619)
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507) ^ Math.imul(h ^ (h >>> 13), 3266489909)
    return ((h ^= h >>> 16) >>> 0) / 4294967296
  }
}

/** Fake students who opted in to individual insight for this unit (rule 3 in AGENTS.md). */
export function demoStudents(unitCode: string): DemoStudent[] | null {
  const unit = DEMO[unitCode]
  if (!unit) return null
  const rand = seeded(unitCode)
  const count = 8
  return Array.from({ length: count }, (_, s) => {
    const ability = (rand() - 0.5) * 0.5 // Stronger and weaker students around the class average.
    let correctAll = 0, assessedAll = 0
    const topics = unit.topics.map(([name, difficulty]) => {
      const assessed = rand() < 0.15 ? 0 : 2 + Math.floor(rand() * 9)
      const p = Math.min(0.97, Math.max(0.05, 1 - difficulty + ability))
      let correct = 0
      for (let i = 0; i < assessed; i++) if (rand() < p) correct++
      correctAll += correct; assessedAll += assessed
      const [ci_low, ci_high] = assessed ? wilson(correct, assessed) : [null, null]
      return { name, assessed, accuracy: assessed ? correct / assessed : null, ci_low, ci_high }
    })
    const [ci_low, ci_high] = wilson(correctAll, assessedAll)
    const days = Math.floor(rand() * 9)
    return {
      label: `Student ${String.fromCharCode(65 + s)}`,
      lastActive: days === 0 ? 'today' : days === 1 ? 'yesterday' : `${days} days ago`,
      sessions: 1 + Math.floor(rand() * 5),
      overall: { accuracy: correctAll / assessedAll, ci_low, ci_high, assessed: assessedAll },
      topics,
    }
  }).sort((a, b) => a.overall.accuracy - b.overall.accuracy)
    .map((student, i) => ({ ...student, label: `Student ${String.fromCharCode(65 + i)}` })) // A = most in need of help.
}
