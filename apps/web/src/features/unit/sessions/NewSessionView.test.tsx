import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { beforeEach, expect, it, vi } from 'vitest'
import { hasPendingSession } from '../../../api/sessions'
import { useRole } from '../../../app/role'
import { useOffering } from '../useOffering'
import { useSessionList } from './sessionStore'
import NewSessionView from './NewSessionView'

vi.mock('../../../api/sessions')
vi.mock('../../../app/role')
vi.mock('../useOffering')
vi.mock('./sessionStore')
vi.mock('../practice/summaryStore')

beforeEach(() => {
  vi.mocked(useRole).mockReturnValue('student')
  vi.mocked(useOffering).mockReturnValue({ id: 'offering', unit: { code: 'TEST', title: 'Test' }, year: 2026, semester: 'Semester 1', suggestions: ['Topic'] })
  vi.mocked(useSessionList).mockReturnValue({ status: 'ready', sessions: [] })
  vi.mocked(hasPendingSession).mockReturnValue(false)
})

const render = () => renderToStaticMarkup(<MemoryRouter><NewSessionView /></MemoryRouter>)

it('offers recovery and prevents alternative goals while a session start is unresolved', () => {
  vi.mocked(hasPendingSession).mockReturnValue(true)
  const html = render()
  expect(html).toContain('Recover previous session')
  expect(html).toContain('avoid duplicates')
  // The topic starter is disabled while the earlier start is unresolved.
  expect(html).toMatch(/<button[^>]*disabled=""[^>]*>(?:(?!<\/button>).)*>Topic<(?:(?!<\/button>).)*<\/button>/)
})

it('does not offer recovery for a fresh request or lecturer view', () => {
  expect(render()).not.toContain('Recover previous session')
  vi.mocked(hasPendingSession).mockReturnValue(true)
  vi.mocked(useRole).mockReturnValue('lecturer')
  expect(render()).not.toContain('Recover previous session')
})
