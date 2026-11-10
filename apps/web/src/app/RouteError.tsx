import { useRevalidator, useRouteError } from 'react-router'
import { ApiError } from '../api/client'
import { Button } from '../components/ui'

export default function RouteError() {
  const error = useRouteError()
  const retry = useRevalidator()
  const deleted = error instanceof ApiError && error.status === 410
  return <section className="m-8 max-w-xl space-y-4" role="alert">
    <h1 className="text-2xl font-semibold">{deleted ? 'Offering deleted' : 'Athena is unavailable'}</h1>
    <p>{error instanceof Error ? error.message : 'The requested study space could not be loaded.'}</p>
    <Button onClick={() => void retry.revalidate()}>Try again</Button>
    <a className="ml-4 text-accent underline" href="/">Back to Offerings</a>
  </section>
}
