import type { Feature } from '../../app/feature'
import ReviewPage from './ReviewPage'

export const reviewFeature: Feature = {
  id: 'review',
  nav: { label: 'Review', to: '/review' },
  routes: [{ path: 'review', element: <ReviewPage /> }],
}
