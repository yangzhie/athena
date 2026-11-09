import type { Feature } from '../../app/feature'
import LibraryPage from './LibraryPage'

export const libraryFeature: Feature = {
  id: 'library',
  nav: { label: 'Library', to: '/library' },
  routes: [{ path: 'library', element: <LibraryPage /> }],
}
