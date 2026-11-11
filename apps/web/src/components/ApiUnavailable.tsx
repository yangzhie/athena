import type { ApiError } from '../api/client'
import { Button, Card } from './ui'

/** Shown when apps/api isn't reachable (status 0) or returns an error. */
export function ApiUnavailable({ error, onRetry, what }: { error: ApiError; onRetry?: () => void; what: string }) {
  const unreachable = error.status === 0
  return (
    <Card title={unreachable ? `${what} isn’t available` : 'Something went wrong'}>
      <p className="text-sm text-muted">{error.message}</p>
      {unreachable && (
        <pre className="mt-3 overflow-x-auto rounded-lg bg-line/40 p-3 text-xs">
          {'From the Athena repository root:\nnpm run dev:all'}
        </pre>
      )}
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Card>
  )
}
