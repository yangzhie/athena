import type { CSSProperties } from 'react'
import { Link, Outlet, useLoaderData } from 'react-router'
import { IdentityContext } from './identity'
import { cn } from '../lib/cn'
import { features } from './features'
import type { layoutLoader } from './layoutLoader'
import { SidebarToggle } from './SidebarToggle'
import { UnitNav } from './UnitNav'
import { useSidebar } from './useSidebar'

const sidebarActions = features.flatMap((f) => (f.sidebarAction ? [{ id: f.id, Action: f.sidebarAction }] : []))

export default function AppLayout() {
  const { offerings, identity } = useLoaderData<typeof layoutLoader>()
  const { open, isDesktop, toggle, closeDrawer } = useSidebar()
  // Phones always have the top bar (the drawer covers it); desktop only when collapsed.
  const showTopBar = !isDesktop || !open

  return (
    <IdentityContext.Provider value={identity}><div
      className="flex min-h-svh"
      // Pages use this to place sticky panels below the top bar (e.g. the sandbox).
      style={{ '--topbar-h': showTopBar ? '4.25rem' : '0px' } as CSSProperties}
    >
      {/* Phone only: dims the page behind the open drawer; tap to close. */}
      {!isDesktop && open && (
        <div className="fixed inset-0 z-20 bg-black/40" onClick={closeDrawer} aria-hidden />
      )}

      <aside
        id="sidebar"
        // Off-screen or zero-width sidebars must not be reachable by Tab.
        inert={!open}
        className={cn(
          'z-30 shrink-0 overflow-hidden border-line bg-surface transition-[width,transform] duration-200 ease-out motion-reduce:transition-none',
          // Phone: drawer that slides over the page.
          'fixed inset-y-0 left-0 w-72 border-r',
          open ? 'translate-x-0' : '-translate-x-full',
          // Desktop: docked, collapses to zero width.
          'md:sticky md:top-0 md:h-svh md:translate-x-0',
          open ? 'md:w-64' : 'md:w-0 md:border-r-0',
        )}
      >
        {/* Fixed inner width so content doesn't squash while the width animates. */}
        <div className="flex h-full w-72 flex-col gap-6 px-4 py-4 md:w-64">
          <div className="flex items-center justify-between">
            <Link to="/" className="px-2 text-lg font-semibold tracking-tight">
              Athena
            </Link>
            <SidebarToggle open={open} onClick={toggle} />
          </div>

          <UnitNav offerings={offerings} onNavigate={closeDrawer} />

          <div className="mt-auto space-y-2">
            {sidebarActions.map(({ id, Action }) => (
              <Action key={id} onNavigate={closeDrawer} />
            ))}
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Always a way to reopen the sidebar. */}
        {showTopBar && (
          <div className="sticky top-0 z-10 flex h-[4.25rem] items-center gap-2 bg-bg/85 px-4 backdrop-blur">
            <SidebarToggle open={open} onClick={toggle} />
            <Link to="/" className="text-lg font-semibold tracking-tight">
              Athena
            </Link>
          </div>
        )}

        <main className={cn('flex flex-1 flex-col px-4 md:px-10', showTopBar ? 'pt-2' : 'pt-6 md:pt-10')}>
          <Outlet />
        </main>
      </div>
    </div></IdentityContext.Provider>
  )
}
