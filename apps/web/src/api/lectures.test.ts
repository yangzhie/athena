import { afterEach, expect, it, vi } from 'vitest'
import { listLectures } from './lectures'

afterEach(() => vi.unstubAllGlobals())
it('keeps an empty published lecture list empty instead of selecting demo clips', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('[]', { status: 200 })))
  expect(await listLectures('cse5alg-2026-s2')).toEqual([])
})
it('reports unavailable lecture APIs without returning fixture material', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
  await expect(listLectures('cse5alg-2026-s2')).rejects.toMatchObject({ status: 0 })
})
