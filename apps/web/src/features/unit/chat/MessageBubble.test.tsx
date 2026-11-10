import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { ChatMessage } from '../../../types'
import { playgroundPath, sessionPath } from '../sessions/paths'
import { MessageBubble } from './MessageBubble'

const message: ChatMessage = {
  id: 'message', role: 'tutor', content: 'Try this', createdAt: '2026-01-01T00:00:00Z',
  playground: { sceneId: 'scene one', title: 'Cleaning', goal: 'Clean the data' },
}
const render = (m = message, viewer: 'student' | 'lecturer' = 'student') => renderToStaticMarkup(
  <MemoryRouter><MessageBubble message={m} offeringId="offering" sessionId="session" viewer={viewer} compact open /></MemoryRouter>,
)

describe('merged message rendering', () => {
  it('labels general and mixed answers without claiming the entire offering lacks coverage', () => {
    const general = render({ ...message, knowledgeOrigin: 'general' })
    expect(general).toContain('material retrieved for this question')
    expect(general).not.toContain('Not found in your unit')
    const mixed = render({ ...message, knowledgeOrigin: 'supplement', sources: [{
      kind: 'document', sourceId: 'slides', passageId: 'page-28', title: 'Prediction', page: 28,
      quote: 'Classification predicts labels.',
    }] })
    expect(mixed).toContain('labelled general-knowledge additions')
    expect(mixed).toContain('Prediction · p. 28')
  })
  it('keeps the session and scene in a Playground recommendation link', () => {
    expect(render()).toContain('href="/units/offering/s/session/playground?scene=scene%20one"')
    expect(render()).toContain('Open Playground')
  })

  it('retains activity cards alongside Playground recommendations in the compact view', () => {
    const html = render({ ...message, activity: { kind: 'explanation', activity_id: 'step', text: 'Agent teaching step' } })
    expect(html).toContain('Agent teaching step')
    expect(html).toContain('Continue')
    expect(html).toContain('Open Playground')
    expect(html).toContain('text-sm leading-relaxed')
  })

  it('labels local demo messages and never renders them for lecturers', () => {
    const local = { ...message, via: 'playground' as const }
    expect(render(local)).toContain('not saved or shared')
    expect(render(local, 'lecturer')).toBe('')
    expect(render({ ...local, role: 'learner' })).toContain('not saved or shared')
  })

  it('keeps lecturer replies and student labels without private environment links', () => {
    expect(render({ ...message, role: 'lecturer' })).toContain('Your lecturer')
    expect(render({ ...message, role: 'lecturer' }, 'lecturer')).toContain('You (lecturer)')
    expect(render({ ...message, role: 'learner' }, 'lecturer')).toContain('Student')
    expect(render(message, 'lecturer')).not.toContain('Open Playground')
    expect(render({ ...message, activity: { kind: 'explanation', activity_id: 'step', text: 'Read only' } }, 'lecturer')).not.toContain('Continue')
  })

  it('encodes identifiers and returns to the same chat, not the unit landing page', () => {
    expect(sessionPath('unit/a', 'session b')).toBe('/units/unit%2Fa/s/session%20b')
    expect(playgroundPath('unit/a', 'session b', 'scene?1')).toBe('/units/unit%2Fa/s/session%20b/playground?scene=scene%3F1')
  })
})
