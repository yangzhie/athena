import { ApiError, call } from './client'

interface PendingOperation { id: string; fingerprint: string }
const memory = new Map<string, PendingOperation>()

function read(key: string): PendingOperation | undefined {
  try {
    const saved = sessionStorage.getItem(key)
    if (saved) return JSON.parse(saved) as PendingOperation
  } catch { /* Storage can be disabled; retain retries within the current page. */ }
  return memory.get(key)
}

function write(key: string, pending?: PendingOperation) {
  if (pending) memory.set(key, pending)
  else memory.delete(key)
  try {
    if (pending) sessionStorage.setItem(key, JSON.stringify(pending))
    else sessionStorage.removeItem(key)
  } catch { /* In-memory retry still works. */ }
}

/** Preserve retry identity after an uncertain response, including tab refresh.
 * Only a digest and random identifier enter tab storage, never the submitted text.
 */
export async function operationCall<T>(path: string, input: object, signal?: AbortSignal): Promise<T> {
  const body = JSON.stringify(input)
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body))
  const fingerprint = Array.from(new Uint8Array(digest), (v) => v.toString(16).padStart(2, '0')).join('')
  const key = `athena-operation:${path}`
  const previous = read(key)
  if (previous && previous.fingerprint !== fingerprint) {
    throw new ApiError(409, 'Refresh to recover the previous submission before starting another operation.')
  }
  const pending = previous ?? { id: crypto.randomUUID(), fingerprint }
  write(key, pending)
  try {
    const result = await call<T>(path, { method: 'POST', body, signal, headers: { 'Idempotency-Key': pending.id } })
    if (read(key)?.id === pending.id) write(key)
    return result
  } catch (error) {
    // Validation/auth failures did not accept this operation. Uncertain results
    // and conflicts retain their key so a retry cannot create duplicate history.
    if (error instanceof ApiError && [400, 401, 403, 404, 413, 422].includes(error.status)) {
      if (read(key)?.id === pending.id) write(key)
    }
    throw error
  }
}

/** Resume a saved server operation after refresh without retaining its private input. */
export async function recoverPendingOperation(path: string, sessionsBase: string) {
  const key = `athena-operation:${path}`
  const pending = read(key)
  if (!pending) return
  const kind = sessionsBase.endsWith('/srs') ? (path.endsWith('/rating') ? 'rating' : 'answer') : path.endsWith('/messages') ? 'message' : 'start'
  try {
    await call(`${sessionsBase}/operations/${encodeURIComponent(`${kind}:${pending.id}`)}/retry`, { method: 'POST' })
    if (read(key)?.id === pending.id) write(key)
  } catch (error) {
    if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
      if (read(key)?.id === pending.id) write(key)
      if (error.status === 404) return // The original request never arrived, or its session was deleted.
    }
    throw error
  }
}

/** Recover committed Practice submissions without storing their private inputs in the tab. */
export async function recoverPracticeOperations(base: string) {
  const keys = new Set(memory.keys())
  try {
    for (let index = 0; index < sessionStorage.length; index++) {
      const key = sessionStorage.key(index)
      if (key) keys.add(key)
    }
  } catch { /* Memory fallback remains available. */ }
  for (const key of keys) {
    const prefix = 'athena-operation:'
    if (!key.startsWith(prefix)) continue
    const path = key.slice(prefix.length)
    if (path === `${base}/attempts` || path.startsWith(`${base}/attempts/`) && path.endsWith('/rating')) {
      await recoverPendingOperation(path, base)
    }
  }
}

export async function recoverPlaygroundTurn(path: string) {
  const key = `athena-operation:${path}`
  const pending = read(key)
  if (!pending) return
  try {
    await call(`${path}/${encodeURIComponent(pending.id)}/retry`, { method: 'POST' })
    write(key)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) { write(key); return }
    throw error
  }
}
