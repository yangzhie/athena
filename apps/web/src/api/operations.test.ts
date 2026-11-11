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

it('recovers a Practice submission after refresh without retaining the answer text', async () => {
  const data = new Map<string, string>()
  vi.stubGlobal('sessionStorage', {
    get length() { return data.size },
    key: (index: number) => [...data.keys()][index] ?? null,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('lost response'))
    .mockResolvedValue({ ok: true, status: 200, json: async () => ({ attempt_id: 'saved' }) })
  vi.stubGlobal('fetch', fetcher)
  const base = '/units/practice-recovery/srs'
  const operations = await import('./operations')
  await expect(operations.operationCall(`${base}/attempts`, { item_id: 'i', variant_id: 'v', answer: 'SENSITIVE ANSWER' })).rejects.toMatchObject({ status: 0 })
  expect([...data.values()].join()).not.toContain('SENSITIVE ANSWER')
  const id = fetcher.mock.calls[0][1].headers['Idempotency-Key']
  vi.resetModules()
  const refreshed = await import('./operations')
  await refreshed.recoverPracticeOperations(base)
  expect(fetcher.mock.calls[1][0]).toBe(`/api${base}/operations/${encodeURIComponent(`answer:${id}`)}/retry`)
  expect(fetcher.mock.calls[1][1].body).toBeUndefined()
  expect(data.size).toBe(0)
  await expect(refreshed.operationCall(`${base}/attempts`, { item_id: 'next', variant_id: 'new', answer: 'different' })).resolves.toMatchObject({ attempt_id: 'saved' })
})

it('recovers only Practice operations in the selected Offering', async () => {
  const data = new Map<string, string>()
  vi.stubGlobal('sessionStorage', {
    get length() { return data.size }, key: (index: number) => [...data.keys()][index] ?? null,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key),
  })
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('lost')).mockRejectedValueOnce(new TypeError('lost'))
    .mockResolvedValue({ ok: true, status: 200, json: async () => ({ next_due_at: 'saved' }) })
  vi.stubGlobal('fetch', fetcher)
  const operations = await import('./operations')
  for (const offering of ['current', 'other']) {
    await expect(operations.operationCall(`/units/${offering}/srs/attempts/attempt/rating`, { rating: 'good' })).rejects.toMatchObject({ status: 0 })
  }
  vi.resetModules()
  const refreshed = await import('./operations')
  await refreshed.recoverPracticeOperations('/units/current/srs')
  expect(fetcher.mock.calls).toHaveLength(3)
  expect(fetcher.mock.calls[2][0]).toContain('/units/current/srs/operations/rating%3A')
  expect([...data.keys()]).toEqual(['athena-operation:/units/other/srs/attempts/attempt/rating'])
})
