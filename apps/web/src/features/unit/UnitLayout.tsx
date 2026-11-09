import { Link, Outlet, useLoaderData } from 'react-router'
import type { unitLoader } from './loader'

/** Shared frame for a unit's views (chat, clips). */
export default function UnitLayout() {
  const { offering } = useLoaderData<typeof unitLoader>()

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

  return <Outlet />
}
