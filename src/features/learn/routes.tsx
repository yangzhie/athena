import type { Feature } from '../../app/feature'
import LearnPage from './LearnPage'

export const learnFeature: Feature = {
  id: 'learn',
  nav: { label: 'Learn', to: '/learn' },
  routes: [
    { path: 'learn', element: <LearnPage /> },
    { path: 'learn/:topicId', element: <LearnPage /> },
  ],
}
