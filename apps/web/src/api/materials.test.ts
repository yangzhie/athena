import { afterEach, expect, it, vi } from 'vitest'
import { uploadMaterial } from './materials'

afterEach(() => vi.unstubAllGlobals())
it('uploads original file bytes without declaring them to be JSON', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{"status":"queued"}', { status: 202 }))
  vi.stubGlobal('fetch', fetch)
  const file = Object.assign(new Blob(['Grounded course passage.'], { type: 'text/plain' }), { name: 'notes.txt' }) as File
  await uploadMaterial('offering', file)
  const [url, options] = fetch.mock.calls[0]
  expect(url).toBe('/api/units/offering/materials?filename=notes.txt')
  expect(options.body).toBe(file)
  expect(options.headers).not.toHaveProperty('Content-Type')
})
