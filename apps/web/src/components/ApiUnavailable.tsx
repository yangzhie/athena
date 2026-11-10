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
          {'cd apps/api\nATHENA_DEV_STUDENT_ID=dev-student ATHENA_DEV_LECTURER_ID=dev-lecturer \\\n  uv run uvicorn athena_api.app:create_app --factory --reload'}
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
