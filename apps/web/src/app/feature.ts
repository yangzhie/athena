import type { ComponentType } from 'react'
import type { RouteObject } from 'react-router'

/**
 * A self-contained slice of the app. Each folder in src/features exports one,
 * and ./features.ts lists them. The router and the sidebar are built from that
 * list, so adding a feature never means editing the layout.
 */
export interface SidebarActionProps {
  /** Call after navigating, so the phone drawer closes. */
  onNavigate?: () => void
}

export interface Feature {
  id: string
  /** Mounted inside AppLayout, so paths are relative (e.g. "units/:offeringId"). */
  routes: RouteObject[]
  /** Optional control pinned to the bottom of the sidebar (e.g. a "create" button). */
  sidebarAction?: ComponentType<SidebarActionProps>
}
