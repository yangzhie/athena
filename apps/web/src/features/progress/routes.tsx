import type { Feature } from '../../app/feature'
import ProgressPage from './ProgressPage'
import { progressLoader } from './loader'

export const progressFeature: Feature = {
  id: 'progress',
  nav: { label: 'Progress', to: '/progress' },
  routes: [{ path: 'progress', element: <ProgressPage />, loader: progressLoader }],
}
