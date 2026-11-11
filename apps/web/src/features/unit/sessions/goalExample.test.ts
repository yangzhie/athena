import { describe, expect, it } from 'vitest'
import { pickGoalExample } from './goalExample'

describe('pickGoalExample', () => {
  it('prefers approved clip titles over broad topics', () => {
    expect(pickGoalExample(['Galvanic cells'], ['Rules for assigning oxidation numbers'], () => 0)).toBe(
      'Rules for assigning oxidation numbers',
    )
  })

  it('falls back to topics when there are no clips', () => {
    expect(pickGoalExample(['Galvanic cells', 'Electrolytic cells'], [], () => 0.99)).toBe('Electrolytic cells')
  })

  it('returns null when the unit has nothing yet', () => {
    expect(pickGoalExample([], [])).toBeNull()
  })

  it('skips blank, duplicate and overly long titles', () => {
    const long = 'x'.repeat(80)
    expect(pickGoalExample([], ['  ', long, 'Newton’s second law', 'Newton’s second law'], () => 0.5)).toBe('Newton’s second law')
  })
})
