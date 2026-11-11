import { describe, expect, it } from 'vitest'
import { demoInsights, demoStudents, wilson } from './demoData'

describe('demo sample data', () => {
  it('computes the same Wilson interval as the API', () => {
    const [low, high] = wilson(5, 8)
    expect(low).toBeCloseTo(0.3057, 3)
    expect(high).toBeCloseTo(0.8632, 3)
  })
  it('is unit-specific, labelled and only for the demo units', () => {
    expect(demoInsights('COMP1001')!.sample_data).toBe(true)
    expect(demoInsights('CHEM1001')!.concepts.map(c => c.name)).toContain('Galvanic cells')
    expect(demoInsights('CSE5DMI')).toBeNull()
    for (const c of demoInsights('PHYS1001')!.concepts) expect(c.ci_low).toBeLessThanOrEqual(c.difficulty_rate)
  })
})

describe('demo opted-in students', () => {
  it('are pseudonymous, unit-specific and stable', () => {
    const students = demoStudents('CHEM1001')!
    expect(students).toHaveLength(8)
    expect(students[0].label).toBe('Student A')
    expect(students[0].topics.map(t => t.name)).toContain('Galvanic cells')
    expect(demoStudents('CHEM1001')).toEqual(students)
    for (const s of students) expect(s.overall.ci_low).toBeLessThanOrEqual(s.overall.accuracy)
    expect(demoStudents('CSE5DMI')).toBeNull()
  })
})
