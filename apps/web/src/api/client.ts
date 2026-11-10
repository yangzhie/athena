/**
 * Calls to apps/api (FastAPI). In dev, Vite proxies /api to it (see vite.config.ts).
 * Identity is decided on the server; the browser never sends a student id.
 */

export class ApiError extends Error {
  /** 0 = the API couldn't be reached at all. */
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function asApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, String(e))
}

export async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError(0, 'The Athena API isn’t reachable.')
  }
  if (res.status === 204) return undefined as T
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    // The Vite proxy answers 5xx with no JSON body when the API isn't running.
    if (res.status >= 500 && !body) throw new ApiError(0, 'The Athena API isn’t reachable.')
    const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${res.status})`
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}
