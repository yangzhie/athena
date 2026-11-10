import type { Feature } from '../../app/feature'
import ChatView from './ChatView'
import { ClipsToggle } from './ClipsToggle'
import ClipsView from './clips/ClipsView'
import { UNIT_ROUTE_ID, clipsLoader, unitLoader } from './loader'
import PlaygroundView from './playground/PlaygroundView'
import ReviewView from './review/ReviewView'
import UnitLayout from './UnitLayout'

export const unitFeature: Feature = {
  id: 'unit',
  routes: [
    {
      id: UNIT_ROUTE_ID,
      path: 'units/:offeringId',
      element: <UnitLayout />,
      loader: unitLoader,
      children: [
        { index: true, element: <ChatView /> },
        { path: 'clips', element: <ClipsView />, loader: clipsLoader },
        { path: 'review', element: <ReviewView />, loader: clipsLoader },
        { path: 'playground', element: <PlaygroundView /> },
      ],
    },
  ],
  sidebarAction: ClipsToggle,
}
