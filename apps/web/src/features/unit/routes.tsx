import InsightsView from './progress/InsightsView'
import LibraryView from './library/LibraryView'
import StudySpaceView from '../spaces/StudySpaceView'
import { Navigate } from 'react-router'
import type { Feature } from '../../app/feature'
import ClipsView from './clips/ClipsView'
import { UNIT_ROUTE_ID, clipsLoader, unitLoader } from './loader'
import PlaygroundView from './playground/PlaygroundView'
import PracticeView from './practice/PracticeView'
import QuestionsReviewView from './questions/QuestionsReviewView'
import ReviewView from './review/ReviewView'
import NewSessionView from './sessions/NewSessionView'
import SharedSessionView from './shared/SharedSessionView'
import SharedSessionsView from './shared/SharedSessionsView'
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
        { path: 'manage', element: <StudySpaceView /> },
        { path: 'library', element: <LibraryView /> },
        { path: 'insights', element: <InsightsView /> },
        { path: 's/:sessionId', element: <SessionView /> },
        { path: 'clips', element: <ClipsView />, loader: clipsLoader },
        { path: 'review', element: <ReviewView />, loader: clipsLoader },
        { path: 's/:sessionId/playground', element: <PlaygroundView /> },
        // Old offering-only links cannot choose a learning session on the student's behalf.
        { path: 'playground', element: <Navigate to=".." replace /> },
        { path: 'practice', element: <PracticeView /> },
        { path: 'questions', element: <QuestionsReviewView /> },
        { path: 'shared', element: <SharedSessionsView /> },
        { path: 'shared/:shareId', element: <SharedSessionView /> },
      ],
    },
  ],
  sidebarAction: UnitViewNav,
}
