import type { Feature } from './feature'
import { homeFeature } from '../features/home/routes'
import { learnFeature } from '../features/learn/routes'
import { reviewFeature } from '../features/review/routes'
import { libraryFeature } from '../features/library/routes'
import { progressFeature } from '../features/progress/routes'

/** Order here is the sidebar order. One line per feature. */
export const features: Feature[] = [
  homeFeature,
  learnFeature,
  reviewFeature,
  libraryFeature,
  progressFeature,
]
