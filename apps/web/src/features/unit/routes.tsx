import type { Feature } from '../../app/feature'
import ClipsView from './clips/ClipsView'
import { UNIT_ROUTE_ID, clipsLoader, unitLoader } from './loader'
import PracticeView from './practice/PracticeView'
import ReviewView from './review/ReviewView'
import NewSessionView from './sessions/NewSessionView'
import SessionView from './sessions/SessionView'
import UnitLayout from './UnitLayout'
import { UnitViewNav } from './UnitViewNav'

export const unitFeature: Feature = {
  id: 'unit',
  routes: [
    {
      id: UNIT_ROUTE_ID,
      path: 'units/:offeringId',
      element: <UnitLayout />,
      loader: unitLoader,
      children: [
        { index: true, element: <NewSessionView /> },
        { path: 's/:sessionId', element: <SessionView /> },
        { path: 'clips', element: <ClipsView />, loader: clipsLoader },
        { path: 'review', element: <ReviewView />, loader: clipsLoader },
        { path: 'practice', element: <PracticeView /> },
      ],
    },
  ],
  sidebarAction: UnitViewNav,
}
