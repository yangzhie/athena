import { createBrowserRouter } from 'react-router'
import AppLayout from './AppLayout'
import RouteError from './RouteError'
import { features } from './features'
import { indexLoader, layoutLoader } from './layoutLoader'
import NoUnits from '../pages/NoUnits'
import NotFound from '../pages/NotFound'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    hydrateFallbackElement: <p role="status" className="p-8 text-sm text-muted">Loading Athena…</p>,
    errorElement: <RouteError />,
    loader: layoutLoader,
    children: [
      { index: true, loader: indexLoader, element: <NoUnits /> },
      ...features.flatMap((f) => f.routes),
      { path: '*', element: <NotFound /> },
    ],
  },
])
