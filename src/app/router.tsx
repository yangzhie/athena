import { createBrowserRouter } from 'react-router'
import AppLayout from './AppLayout'
import NotFound from '../pages/NotFound'
import Placeholder from '../pages/Placeholder'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Placeholder title="Home" /> },
      { path: 'learn', element: <Placeholder title="Learn" /> },
      { path: 'review', element: <Placeholder title="Review" /> },
      { path: 'library', element: <Placeholder title="Library" /> },
      { path: 'progress', element: <Placeholder title="Progress" /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])
