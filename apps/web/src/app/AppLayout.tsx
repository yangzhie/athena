import { NavLink, Outlet } from 'react-router'
import { features } from './features'

const nav = features.flatMap((f) => (f.nav ? [f.nav] : []))

function navClass({ isActive }: { isActive: boolean }) {
  return [
    'rounded-md px-3 py-2 text-sm font-medium transition-colors',
    isActive ? 'bg-accent-soft text-accent' : 'text-muted hover:bg-line/60 hover:text-ink',
  ].join(' ')
}

export default function AppLayout() {
  return (
    <div className="flex min-h-svh flex-col md:flex-row">
      <aside className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-line bg-surface px-4 py-3 md:w-56 md:flex-col md:items-stretch md:border-r md:border-b-0 md:py-6">
        <div className="mr-4 text-lg font-semibold tracking-tight md:mr-0 md:mb-6 md:px-3">Athena</div>
        <nav className="flex gap-1 md:flex-col">
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="flex-1 px-4 py-6 md:px-10 md:py-10">
        <Outlet />
      </main>
    </div>
  )
}
