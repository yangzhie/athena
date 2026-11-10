import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useRole } from '../../../app/role'
import { ApiError } from '../../../api/client'
import { useThread } from '../chat/chatStore'
import { useOffering } from '../useOffering'
import { SessionGate } from './SessionGate'

vi.mock('../../../app/role')
vi.mock('../useOffering')
vi.mock('../chat/chatStore')

beforeEach(() => {
  vi.mocked(useRole).mockReturnValue('student')
  vi.mocked(useOffering).mockReturnValue({ id: 'offering', unit: { code: 'TEST', title: 'Test' }, year: 2026, semester: 'Semester 1', suggestions: [] })
  vi.mocked(useThread).mockReturnValue({
    status: 'ready', sending: false, messages: [],
    session: { id: 'session', offeringId: 'offering', title: 'Private', goal: 'Private', shared: false, createdAt: '', updatedAt: '' },
  })
})
const render = (path = '/units/offering/s/session/playground') => renderToStaticMarkup(
  <MemoryRouter initialEntries={[path]}>
    <Routes><Route path="units/:offeringId/s/:sessionId/playground" element={<SessionGate>{() => <p>Private canvas</p>}</SessionGate>} /></Routes>
  </MemoryRouter>,
)

describe('Playground session gate', () => {
  it('opens only the matching learning session', () => {
    expect(render()).toContain('Private canvas')
    expect(render('/units/offering/s/another-session/playground')).not.toContain('Private canvas')
  })
  it('does not render cached data belonging to another offering', () => {
    const thread = useThread('session')
    vi.mocked(useThread).mockReturnValue({ ...thread, session: { ...thread.session!, offeringId: 'another-offering' } })
    expect(render()).toContain('Session not found')
    expect(render()).not.toContain('Private canvas')
  })
  it('does not render a student environment in lecturer mode', () => {
    vi.mocked(useRole).mockReturnValue('lecturer')
    expect(render()).toContain('Learning sessions are private')
    expect(render()).not.toContain('Private canvas')
  })
  it('does not instantiate a canvas before the API session is available', () => {
    vi.mocked(useThread).mockReturnValue({ status: 'loading', sending: false, messages: [] })
    expect(render()).toContain('Loading')
    vi.mocked(useThread).mockReturnValue({ status: 'error', sending: false, messages: [], error: new ApiError(0, 'Offline') })
    expect(render()).not.toContain('Private canvas')
    vi.mocked(useThread).mockReturnValue({ status: 'missing', sending: false, messages: [] })
    expect(render()).toContain('Session not found')
  })
})
