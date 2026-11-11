import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { IdentityContext } from '../../app/identity'
import { setRole } from '../../app/role'
import { CreateSpaceButton } from './CreateSpaceButton'
import { RoleSwitch } from '../role/RoleSwitch'

vi.mock('../../lib/persistedStore', () => ({ createPersistedStore: (_key: string, initial: string) => { let value = initial; return { use: () => value, set: (next: string) => { value = next } } } }))
vi.mock('react-router', () => ({ useNavigate: () => vi.fn(), useRevalidator: () => ({ revalidate: vi.fn() }) }))
beforeEach(() => setRole('student'))
const render = (role: 'student' | 'lecturer') => renderToStaticMarkup(<IdentityContext.Provider value={{ anonymous: true, role }}><CreateSpaceButton /><RoleSwitch /></IdentityContext.Provider>)

describe('lecturer-only course creation', () => {
  it('hides creation and lecturer navigation from students even with a forged view preference', () => {
    setRole('lecturer')
    const html = render('student')
    expect(html).not.toContain('+ New study space')
    expect(html).not.toContain('role="radio"')
    expect(html).toContain('Lecturer invite code')
  })
  it('shows creation only in an authorised lecturer view', () => {
    expect(render('lecturer')).not.toContain('+ New study space')
    setRole('lecturer')
    expect(render('lecturer')).toContain('+ New study space')
    expect(render('lecturer')).toContain('role="radio"')
  })
})
