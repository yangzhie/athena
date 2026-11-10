import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getCanvas } from '../../../api/playground'
import type { LearningSession, Offering } from '../../../types'
import { forgetThread, getThread, seedThread } from '../chat/chatStore'
import { forgetPlayground, openScene, sessionFor } from './session'

vi.mock('../../../api/playground', async (importOriginal) => ({
  ...await importOriginal<typeof import('../../../api/playground')>(),
  getCanvas: vi.fn(),
}))

const offering: Offering = { id: 'offering-a', unit: { code: 'TEST', title: 'Test' }, year: 2026, semester: 'Semester 1', suggestions: [] }
const session: LearningSession = {
  id: 'canvas-a', offeringId: offering.id, goal: 'Cleaning', title: 'Cleaning',
  createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z', shared: false,
}
beforeEach(() => {
  vi.clearAllMocks()
  seedThread(session, [])
  seedThread({ ...session, id: 'canvas-b' }, [])
})
afterEach(() => {
  for (const id of ['canvas-a', 'canvas-b']) { forgetPlayground(id); forgetThread(id) }
})

describe('session-scoped Playground', () => {
  it('isolates canvases in the same offering and retains the viewport on returning', () => {
    const a = sessionFor(offering, 'canvas-a')
    const b = sessionFor(offering, 'canvas-b')
    const beforeB = b.playground.getState().viewport
    const viewport = { x: 12, y: 34, zoom: 1.4 }
    a.playground.setViewport(viewport)
    expect(a.playground).not.toBe(b.playground)
    expect(sessionFor(offering, 'canvas-a')).toBe(a)
    expect(sessionFor(offering, 'canvas-a').playground.getState().viewport).toBe(viewport)
    expect(b.playground.getState().viewport).toBe(beforeB)
  })

  it('will not open a missing session or one from another offering', () => {
    expect(() => sessionFor(offering, 'not-loaded')).toThrow('Load this learning session')
    expect(() => sessionFor({ ...offering, id: 'other-offering' }, 'canvas-a')).toThrow('Load this learning session')
  })

  it('keeps unavailable state visible and never invents browser-local tutor messages', async () => {
    vi.mocked(getCanvas).mockRejectedValue(new Error('Playground unavailable'))
    await openScene(offering, 'canvas-a', 'missing-scene')
    await openScene(offering, 'canvas-a', 'missing-scene')
    expect(getCanvas).toHaveBeenCalledTimes(2)
    expect(sessionFor(offering, 'canvas-a').sceneId).toBeNull()
    expect(getThread('canvas-a').messages).toEqual([])
    expect(getThread('canvas-b').messages).toEqual([])
  })

  it('does not reuse a disposed canvas', () => {
    const before = sessionFor(offering, 'canvas-a')
    forgetPlayground('canvas-a')
    expect(sessionFor(offering, 'canvas-a')).not.toBe(before)
  })
})
