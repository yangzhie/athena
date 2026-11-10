import { useEffect } from 'react'
import { NavLink, useMatch } from 'react-router'
import type { SidebarActionProps } from '../../app/feature'
import { useRole } from '../../app/role'
import { cn } from '../../lib/cn'
import { refreshSrsSummary, useSrsSummary } from './practice/summaryStore'
import { useSessions } from './sessions/sessionStore'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors',
    isActive ? 'bg-accent-soft text-accent' : 'text-muted hover:bg-line/60 hover:text-ink',
  )

/**
 * The open unit's navigation.
 * Students: their learning sessions, then lecture clips and practice.
 * Lecturers: clip review (students' sessions are private).
 */
export function UnitViewNav({ onNavigate }: SidebarActionProps) {
  const role = useRole()
  const unit = useMatch('/units/:offeringId/*')
  const id = unit?.params.offeringId ?? ''
  const summary = useSrsSummary(id)
  const sessions = useSessions(id)

  useEffect(() => {
    if (id && role === 'student') void refreshSrsSummary(id)
  }, [id, role])

  if (!id) return null
  const due = summary ? summary.due_now + summary.new_available : 0

  if (role === 'lecturer') {
    return (
      <nav aria-label="This unit" className="space-y-0.5">
        <NavLink to={`/units/${id}/review`} onClick={onNavigate} className={linkClass}>
          <span aria-hidden>🎬</span> Review clips
        </NavLink>
      </nav>
    )
  }

  return (
    <nav aria-label="This unit" className="space-y-3">
      <div>
        <p className="mb-1 px-3 text-xs font-medium tracking-wide text-muted uppercase">Sessions</p>
        <NavLink to={`/units/${id}`} end onClick={onNavigate} className={linkClass}>
          <span aria-hidden>＋</span> New session
        </NavLink>
        {sessions.length > 0 && (
          <ul className="mt-0.5 max-h-56 space-y-0.5 overflow-y-auto">
            {sessions.map((s) => (
              <li key={s.id}>
                <NavLink to={`/units/${id}/s/${s.id}`} onClick={onNavigate} className={linkClass} title={s.goal}>
                  <span className="truncate">{s.title}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-0.5 border-t border-line pt-3">
        <NavLink to={`/units/${id}/clips`} onClick={onNavigate} className={linkClass}>
          <span aria-hidden>🎬</span> Lecture clips
        </NavLink>
        <NavLink to={`/units/${id}/practice`} onClick={onNavigate} className={linkClass}>
          <span aria-hidden>🧠</span> Practice
          {due > 0 && (
            <span
              className="ml-auto rounded-full bg-accent px-1.5 text-xs font-medium text-white tabular-nums"
              aria-label={`${due} to review`}
            >
              {due}
            </span>
          )}
        </NavLink>
      </div>
    </nav>
  )
}
