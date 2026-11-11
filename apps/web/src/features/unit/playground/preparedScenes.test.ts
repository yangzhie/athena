import { describe, expect, it } from 'vitest'
import { isPrepared, preparedFor } from './preparedScenes'

describe('prepared Playground scenes for the demo units', () => {
  it('offers each demo unit its own experiments', () => {
    expect(preparedFor('COMP1001').map((s) => s.id)).toEqual(['bubble-sort', 'cleaning-average'])
    expect(preparedFor('PHYS1001')[0].id).toBe('pendulum-g')
    expect(preparedFor('CHEM1001')[0]).toMatchObject({ id: 'galvanic-cells', title: 'Galvanic cells' })
    expect(preparedFor('CSE5DMI')).toEqual([])
  })
  it('puts the experiment that fits the lesson goal first', () => {
    expect(preparedFor('PHYS1001', 'Photoelectric effect and photons')[0].id).toBe('photoelectric-planck')
    expect(preparedFor('CHEM1001', 'Titration practice')[0].id).toBe('naoh-standardisation')
    expect(preparedFor('COMP1001', 'Testing bubble sort')[0].id).toBe('bubble-sort')
  })
  it('knows which scene ids can be opened without a model', () => {
    expect(isPrepared('bubble-sort')).toBe(true)
    expect(isPrepared('model-made-scene')).toBe(false)
  })
})
