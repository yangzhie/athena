import type { Feature } from '../../app/feature'
import ChatView from './ChatView'
import { ClipsToggle } from './ClipsToggle'
import ClipsView from './clips/ClipsView'
import { UNIT_ROUTE_ID, clipsLoader, unitLoader } from './loader'
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
      ],
    },
  ],
  sidebarAction: ClipsToggle,
}
