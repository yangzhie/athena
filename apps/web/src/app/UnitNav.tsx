import type { CSSProperties } from 'react'
import { NavLink } from 'react-router'
import { cn } from '../lib/cn'
import { unitColor } from '../lib/unitColor'
import type { Offering } from '../types'

/** The units, as coloured index tabs down the notebook's edge. */
export function UnitNav({ offerings, onNavigate }: { offerings: Offering[]; onNavigate?: () => void }) {
  return (
    <nav aria-label="Your units">
      <p className="mb-2 px-2 text-xs font-semibold tracking-[0.14em] text-muted uppercase">Your units</p>
      {offerings.length === 0 ? (
        <p className="px-2 text-sm text-muted">No units yet.</p>
      ) : (
        <ul className="space-y-1">
          {offerings.map((o) => (
            <li key={o.id}>
              <NavLink
                to={o.status === 'draft' ? `/units/${o.id}/manage` : `/units/${o.id}`}
                onClick={onNavigate}
                style={{ '--tab': unitColor(o.unit.code) } as CSSProperties}
                className={({ isActive }) =>
                  cn(
                    'group relative block rounded-r-md py-2 pr-3 pl-5 transition-colors',
                    // The tab: a coloured strip that widens on the open unit.
                    'before:absolute before:inset-y-1.5 before:left-0 before:rounded-r-sm before:bg-(--tab) before:transition-all',
                    isActive ? 'bg-bg before:w-2' : 'before:w-1 hover:bg-bg/70',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span className="block text-xs font-semibold tracking-[0.12em] text-(--tab) uppercase">
                      {o.unit.code}{o.status === 'draft' ? ' · Draft' : ''}
                    </span>
                    <span className={cn('block truncate font-serif text-[0.95rem] leading-snug', isActive ? 'text-ink' : 'text-ink/80')}>
                      {o.unit.title}
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </nav>
  )
}
