import { useEffect } from 'react'
import { NavLink, useMatch } from 'react-router'
import type { SidebarActionProps } from '../../app/feature'
import { useRole } from '../../app/role'
import { Icon } from '../../components/ui'
import { cn } from '../../lib/cn'
import { refreshSrsSummary, useSrsSummary } from './practice/summaryStore'
import { hasNewReply, useSeen } from './sessions/seenStore'
import { refreshSessions, useSessionList } from './sessions/sessionStore'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex items-center gap-2 rounded-md px-3 py-1.5 text-[0.95rem] transition-colors',
    isActive ? 'font-semibold text-ink [&_.label]:highlight' : 'text-muted hover:bg-bg hover:text-ink',
  )

/**
 * The open unit's navigation.
 * Students: their learning sessions, then lecture clips and practice.
 * Lecturers: clip and question review, and sessions students chose to share.
 */
export function UnitViewNav({ onNavigate }: SidebarActionProps) {
  const role = useRole()
  const unit = useMatch('/units/:offeringId/*')
  const id = unit?.params.offeringId ?? ''
  const summary = useSrsSummary(id)
  const { sessions } = useSessionList(id)
  const seen = useSeen()

  useEffect(() => {
    if (!id || role !== 'student') return
    void refreshSrsSummary(id)
    void refreshSessions(id)
    // Pick up lecturer replies (and due reviews) when the student comes back to the tab.
    const onFocus = () => {
      void refreshSessions(id)
      void refreshSrsSummary(id)
    }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [id, role])

  if (!id) return null
  const due = summary ? summary.due_now + summary.new_available : 0

  if (role === 'lecturer') {
    return (
      <nav aria-label="This unit" className="space-y-0.5">
        <NavLink to={`/units/${id}/insights`} onClick={onNavigate} className={linkClass}>
          <Icon name="chart" /> <span className="label">Offering insights</span>
        </NavLink>
        <NavLink to={`/units/${id}/review`} onClick={onNavigate} className={linkClass}>
          <Icon name="film" /> <span className="label">Review clips</span>
        </NavLink>
        <NavLink to={`/units/${id}/questions`} onClick={onNavigate} className={linkClass}>
          <Icon name="list" /> <span className="label">Review questions</span>
        </NavLink>
        <NavLink to={`/units/${id}/shared`} onClick={onNavigate} className={linkClass}>
          <Icon name="chat" /> <span className="label">Shared sessions</span>
        </NavLink>
      </nav>
    )
  }

  return (
    <nav aria-label="This unit" className="space-y-3">
      <div>
        <p className="mb-1 px-3 text-xs font-semibold tracking-[0.14em] text-muted uppercase">Sessions</p>
        <NavLink to={`/units/${id}`} end onClick={onNavigate} className={linkClass}>
          <Icon name="plus" /> <span className="label">New session</span>
        </NavLink>
        {sessions.length > 0 && (
          <ul className="mt-0.5 max-h-56 space-y-0.5 overflow-y-auto">
            {sessions.map((s) => (
              <li key={s.id}>
                <NavLink to={`/units/${id}/s/${s.id}`} onClick={onNavigate} className={linkClass} title={s.goal}>
                  <span className="label truncate">{s.title}</span>
                  {s.shared && (
                    <span className="ml-auto shrink-0 text-xs" title="Shared with your lecturer" aria-label="shared with your lecturer">
                      👁
                    </span>
                  )}
                  {hasNewReply(s, seen) && (
                    <span
                      className={cn('size-2 shrink-0 rounded-full bg-accent', !s.shared && 'ml-auto')}
                      title="New reply from your lecturer"
                      role="img"
                      aria-label="new reply from your lecturer"
                    />
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-0.5 border-t border-line pt-3">
        <NavLink to={`/units/${id}/library`} onClick={onNavigate} className={linkClass}>
          <Icon name="book" /> <span className="label">Material library</span>
        </NavLink>
        <NavLink to={`/units/${id}/clips`} onClick={onNavigate} className={linkClass}>
          <Icon name="film" /> <span className="label">Lecture clips</span>
        </NavLink>
        <NavLink to={`/units/${id}/practice`} onClick={onNavigate} className={linkClass}>
          <Icon name="cards" /> <span className="label">Practice</span>
          {due > 0 && (
            <span
              className="ml-auto rounded-full bg-margin px-1.5 text-xs font-semibold text-surface tabular-nums"
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
