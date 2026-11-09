import type { Feature } from './feature'
import { roleFeature } from '../features/role/routes'
import { spacesFeature } from '../features/spaces/routes'
import { unitFeature } from '../features/unit/routes'

/** One line per feature. */
export const features: Feature[] = [unitFeature, spacesFeature, roleFeature]
