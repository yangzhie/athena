import type { Feature } from '../../app/feature'
import LearnIndexPage from './LearnIndexPage'
import LearnPage from './LearnPage'
import { learnIndexLoader, learnSessionLoader } from './loader'

export const learnFeature: Feature = {
  id: 'learn',
  nav: { label: 'Learn', to: '/learn' },
  routes: [
    { path: 'learn', element: <LearnIndexPage />, loader: learnIndexLoader },
    { path: 'learn/:topicId', element: <LearnPage />, loader: learnSessionLoader },
  ],
}
