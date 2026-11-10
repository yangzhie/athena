import { afterEach, expect, it, vi } from 'vitest'
import { ApiError } from './client'
import { operationCall } from './operations'

afterEach(() => vi.unstubAllGlobals())

it('reuses the key after a lost response and refresh, then allocates a fresh key', async () => {
  const data = new Map<string, string>()
  vi.stubGlobal('sessionStorage', {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => data.set(k, v),
    removeItem: (k: string) => data.delete(k),
  })
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('lost response'))
    .mockResolvedValue({ ok: true, status: 200, json: async () => ['saved'] })
  vi.stubGlobal('fetch', fetcher)
  const path = '/retry-test'
  await expect(operationCall(path, { text: 'private' })).rejects.toBeInstanceOf(ApiError)
  const key = fetcher.mock.calls[0][1].headers['Idempotency-Key']
  expect([...data.values()].join()).not.toContain('private')
  vi.resetModules() // Simulate a refresh; only sessionStorage remains.
  const refreshed = await import('./operations')
  await expect(refreshed.operationCall(path, { text: 'different' })).rejects.toMatchObject({ status: 409 })
  expect(await refreshed.operationCall(path, { text: 'private' })).toEqual(['saved'])
  expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).toBe(key)
  await refreshed.operationCall(path, { text: 'private' })
  expect(fetcher.mock.calls[2][1].headers['Idempotency-Key']).not.toBe(key)
  expect(data.size).toBe(0)
})

it('clears a rejected validation attempt so the learner can correct it', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: false, status: 400, json: async () => ({ detail: 'invalid' }) })
    .mockResolvedValue({ ok: true, status: 200, json: async () => [] })
  vi.stubGlobal('fetch', fetcher)
  await expect(operationCall('/validation-test', { text: 'wrong' })).rejects.toMatchObject({ status: 400 })
  await expect(operationCall('/validation-test', { text: 'corrected' })).resolves.toEqual([])
  expect(fetcher.mock.calls[0][1].headers['Idempotency-Key']).not.toBe(fetcher.mock.calls[1][1].headers['Idempotency-Key'])
})

it('recovers a pending exchange by server-owned input after refresh', async () => {
  const data = new Map<string, string>()
  vi.stubGlobal('sessionStorage', {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => data.set(k, v),
    removeItem: (k: string) => data.delete(k),
  })
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('lost response'))
    .mockResolvedValue({ ok: true, status: 200, json: async () => ({ messages: ['saved'] }) })
  vi.stubGlobal('fetch', fetcher)
  const path = '/units/test/sessions/one/messages'
  await expect(operationCall(path, { text: 'private question' })).rejects.toBeInstanceOf(ApiError)
  const id = fetcher.mock.calls[0][1].headers['Idempotency-Key']
  vi.resetModules()
  const { recoverPendingOperation } = await import('./operations')
  await recoverPendingOperation(path, '/units/test/sessions')
  expect(fetcher.mock.calls[1][0]).toBe(`/api/units/test/sessions/operations/${encodeURIComponent(`message:${id}`)}/retry`)
  expect(fetcher.mock.calls[1][1].body).toBeUndefined()
  expect(data.size).toBe(0)
})

it('clears an operation that never reached the server', async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('offline'))
    .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: 'missing' }) })
    .mockResolvedValue({ ok: true, status: 200, json: async () => [] })
  vi.stubGlobal('fetch', fetcher)
  const operations = await import('./operations')
  await expect(operations.operationCall('/not-arrived', { goal: 'Goal' })).rejects.toMatchObject({ status: 0 })
  await expect(operations.recoverPendingOperation('/not-arrived', '/not-arrived')).resolves.toBeUndefined()
  await expect(operations.operationCall('/not-arrived', { goal: 'Changed goal' })).resolves.toEqual([])
})
