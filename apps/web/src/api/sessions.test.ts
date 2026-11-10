import { afterEach, expect, it, vi } from 'vitest'

afterEach(() => vi.unstubAllGlobals())

function setup() {
  vi.resetModules()
  const data = new Map<string, string>()
  vi.stubGlobal('sessionStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  return data
}

const saved = {
  session: { id: 'original', offering_id: 'offering', goal: 'Original goal', title: 'Original goal', shared: false, created_at: '', updated_at: '' },
  messages: [{ id: 'opening', role: 'tutor', content: 'Opening question', created_at: '' }],
}
const ok = (value: unknown) => ({ ok: true, status: 200, json: async () => value })

it('recovers the original session after a failed start without submitting a different goal', async () => {
  const data = setup()
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('lost response'))
    .mockResolvedValue(ok(saved))
  vi.stubGlobal('fetch', fetcher)
  const api = await import('./sessions')
  await expect(api.createSession('offering', 'Original goal')).rejects.toMatchObject({ status: 0 })
  expect(api.hasPendingSession('offering')).toBe(true)
  await expect(api.createSession('offering', 'Changed goal')).rejects.toMatchObject({ status: 409 })
  expect(fetcher).toHaveBeenCalledTimes(1)
  const id = fetcher.mock.calls[0][1].headers['Idempotency-Key']
  expect(await api.recoverSession('offering')).toMatchObject({ session: { id: 'original', goal: 'Original goal' }, messages: [{ content: 'Opening question' }] })
  expect(fetcher.mock.calls[1][0]).toBe(`/api/units/offering/sessions/operations/start%3A${id}/retry`)
  expect(fetcher.mock.calls[1][1].body).toBeUndefined()
  expect(data.size).toBe(0)
  expect(api.hasPendingSession('offering')).toBe(false)
})

it('retains recovery after tutor unavailability and permits retry after configuration is fixed', async () => {
  setup()
  const unavailable = { ok: false, status: 503, json: async () => ({ detail: 'Tutor unavailable' }) }
  const fetcher = vi.fn().mockResolvedValueOnce(unavailable).mockResolvedValueOnce(unavailable).mockResolvedValue(ok(saved))
  vi.stubGlobal('fetch', fetcher)
  const api = await import('./sessions')
  await expect(api.createSession('offering', 'Original goal')).rejects.toMatchObject({ status: 503 })
  await expect(api.recoverSession('offering')).rejects.toMatchObject({ status: 503, message: 'Tutor unavailable' })
  expect(api.hasPendingSession('offering')).toBe(true)
  await expect(api.recoverSession('offering')).resolves.toMatchObject({ session: { id: 'original' } })
  expect(api.hasPendingSession('offering')).toBe(false)
})

it('unblocks a fresh goal only when the server confirms the old request is absent', async () => {
  setup()
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('offline'))
    .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: 'missing' }) })
    .mockResolvedValue(ok(saved))
  vi.stubGlobal('fetch', fetcher)
  const api = await import('./sessions')
  await expect(api.createSession('offering', 'Original goal')).rejects.toMatchObject({ status: 0 })
  await expect(api.recoverSession('offering')).resolves.toBeUndefined()
  expect(api.hasPendingSession('offering')).toBe(false)
  await api.createSession('offering', 'Changed goal')
  expect(fetcher.mock.calls[2][1].headers['Idempotency-Key']).not.toBe(fetcher.mock.calls[0][1].headers['Idempotency-Key'])
})

it('shares recovery between background list refresh and the recover button', async () => {
  setup()
  let finish!: (value: ReturnType<typeof ok>) => void
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('lost response'))
    .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    .mockResolvedValue(ok([saved.session]))
  vi.stubGlobal('fetch', fetcher)
  const api = await import('./sessions')
  await expect(api.createSession('offering', 'Original goal')).rejects.toMatchObject({ status: 0 })
  const list = api.listSessions('offering')
  const recovered = api.recoverSession('offering')
  expect(fetcher).toHaveBeenCalledTimes(2)
  finish(ok(saved))
  await expect(recovered).resolves.toMatchObject({ session: { id: 'original' } })
  await expect(list).resolves.toMatchObject([{ id: 'original' }])
  expect(fetcher).toHaveBeenCalledTimes(3) // start, one recovery, list
})

it('clears a definitive recovery rejection so a corrected request can be submitted', async () => {
  setup()
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('lost response'))
    .mockResolvedValueOnce({ ok: false, status: 422, json: async () => ({ detail: 'Invalid goal' }) })
    .mockResolvedValue(ok(saved))
  vi.stubGlobal('fetch', fetcher)
  const api = await import('./sessions')
  await expect(api.createSession('offering', 'Rejected goal')).rejects.toMatchObject({ status: 0 })
  await expect(api.recoverSession('offering')).rejects.toMatchObject({ status: 422 })
  expect(api.hasPendingSession('offering')).toBe(false)
  await expect(api.createSession('offering', 'Corrected goal')).resolves.toMatchObject({ session: { id: 'original' } })
})
