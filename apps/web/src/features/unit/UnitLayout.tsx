import { Link, Outlet, useLoaderData, useMatch } from 'react-router'
import type { unitLoader } from './loader'
import { SidePanel } from './panel/SidePanel'

/** Shared frame for a unit's views (chat, clips, Playground): the view on the left, the side panel on the right. */
export default function UnitLayout() {
  const { offering } = useLoaderData<typeof unitLoader>()
  // The Playground brings its own tutor column instead of the side panel.
  const onPlayground = useMatch('/units/:offeringId/playground')

  if (!offering) {
    return (
      <section className="pb-10">
        <h1 className="text-2xl font-semibold tracking-tight">Unit not found</h1>
        <p className="mt-2 text-muted">You're not enrolled in this unit, or it doesn't exist.</p>
        <Link to="/" className="mt-2 inline-block text-accent hover:underline">
          Back to your units
        </Link>
      </section>
    )
  }

  return (
    <div className="flex flex-1 gap-8">
      <div className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </div>
      {!onPlayground && <SidePanel key={offering.id} offering={offering} />}
    </div>
  )
}
