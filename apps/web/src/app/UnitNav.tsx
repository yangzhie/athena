import { NavLink } from 'react-router'
import { cn } from '../lib/cn'
import type { Offering } from '../types'

export function UnitNav({ offerings, onNavigate }: { offerings: Offering[]; onNavigate?: () => void }) {
  return (
    <nav aria-label="Your units">
      <p className="mb-2 px-2 text-xs font-medium tracking-wide text-muted uppercase">Your units</p>
      {offerings.length === 0 ? (
        <p className="px-2 text-sm text-muted">No units yet.</p>
      ) : (
        <ul className="space-y-1">
          {offerings.map((o) => (
            <li key={o.id}>
              <NavLink
                to={`/units/${o.id}`}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'block rounded-lg px-3 py-2 transition-colors',
                    isActive ? 'bg-accent-soft text-accent' : 'hover:bg-line/60',
                  )
                }
              >
                <span className="block text-sm font-semibold">{o.unit.code}</span>
                <span className="block truncate text-xs text-muted">{o.unit.title}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </nav>
  )
}
