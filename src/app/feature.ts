import type { RouteObject } from 'react-router'

/**
 * A self-contained slice of the app. Each folder in src/features exports one.
 * The router and the sidebar are both built from the list in ./features.ts,
 * so adding a feature never means editing the layout.
 */
export interface Feature {
  id: string
  /** Sidebar entry. Omit for features that have routes but no nav item. */
  nav?: { label: string; to: string; end?: boolean }
  /** Mounted inside AppLayout, so paths are relative (e.g. "review"). */
  routes: RouteObject[]
}
