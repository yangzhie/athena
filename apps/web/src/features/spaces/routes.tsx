import type { Feature } from '../../app/feature'
import { CreateSpaceButton } from './CreateSpaceButton'

/**
 * Study spaces: lecturer-owned spaces for a unit offering (design doc: "Offering").
 * Only the create button for now; list/detail routes come with the backend.
 */
export const spacesFeature: Feature = {
  id: 'spaces',
  routes: [],
  sidebarAction: CreateSpaceButton,
}
