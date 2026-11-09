import type { Feature } from '../../app/feature'
import HomePage from './HomePage'

export const homeFeature: Feature = {
  id: 'home',
  nav: { label: 'Home', to: '/', end: true },
  routes: [{ index: true, element: <HomePage /> }],
}
