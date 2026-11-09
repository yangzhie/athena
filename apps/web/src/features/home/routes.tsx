import type { Feature } from '../../app/feature'
import HomePage from './HomePage'
import { homeLoader } from './loader'

export const homeFeature: Feature = {
  id: 'home',
  nav: { label: 'Home', to: '/', end: true },
  routes: [{ index: true, element: <HomePage />, loader: homeLoader }],
}
