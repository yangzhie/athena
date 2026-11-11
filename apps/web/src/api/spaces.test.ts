import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './client'
import { createStudySpace, getEnrolledOffering, listEnrolledOfferings, publishStudySpace } from './spaces'

afterEach(() => vi.unstubAllGlobals())

describe('persistent study spaces', () => {
  it('loads the server offering list without hardcoded enrolments', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    expect(await listEnrolledOfferings()).toEqual([])
    expect(fetch.mock.calls[0][0]).toBe('/api/offerings')
  })
  it('distinguishes unpublished/missing offerings from deleted or unavailable services', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response('{"detail":"not published"}', { status: 404 }))
      .mockResolvedValueOnce(new Response('{"detail":"deleted"}', { status: 410 }))
      .mockRejectedValueOnce(new Error('offline'))
    vi.stubGlobal('fetch', fetch)
    expect(await getEnrolledOffering('draft')).toBeUndefined()
    await expect(getEnrolledOffering('deleted')).rejects.toMatchObject({ status: 410 })
    await expect(listEnrolledOfferings()).rejects.toBeInstanceOf(ApiError)
  })
  it('creates and publishes using the browser identity without supplied owner identifiers', async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response('{"id":"new-space"}', { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    const input = { code: 'CSE5DMI', title: 'Data Mining', year: 2026, semester: 'Semester 2' }
    await createStudySpace(input)
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(input)
    await publishStudySpace('new-space')
    expect(fetch.mock.calls[1][0]).toBe('/api/offerings/new-space/publish')
  })
})
