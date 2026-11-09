import { createBrowserRouter } from 'react-router'
import AppLayout from './AppLayout'
import { features } from './features'
import NotFound from '../pages/NotFound'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      ...features.flatMap((f) => f.routes),
      { path: '*', element: <NotFound /> },
    ],
  },
])
