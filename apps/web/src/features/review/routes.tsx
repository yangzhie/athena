import type { Feature } from '../../app/feature'
import ReviewPage from './ReviewPage'
import { reviewLoader } from './loader'

export const reviewFeature: Feature = {
  id: 'review',
  nav: { label: 'Review', to: '/review' },
  routes: [{ path: 'review', element: <ReviewPage />, loader: reviewLoader }],
}
