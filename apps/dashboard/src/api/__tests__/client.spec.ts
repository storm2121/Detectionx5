import { afterEach, describe, expect, it } from 'vitest'

import { fakeFetch, png } from '@/__tests__/helpers'

import {
  ApiError,
  api,
  cropUrl,
  describeError,
  errorMessage,
  jobEventsUrl,
  serviceUrl,
  setFetch,
} from '../client'

afterEach(() => setFetch(null))

describe('the service client', () => {
  it('posts photos as multipart form data with the detect flag', async () => {
    const { calls } = fakeFetch([{ method: 'POST', path: '/api/read', body: { id: 'r1' } }])
    const out = await api.read([png('a.png'), png('b.png')], false)
    expect(out).toEqual({ id: 'r1' })
    const [call] = calls
    expect(call?.url).toBe('/api/read?detect=false')
    const body = call?.init?.body as FormData
    expect(body.getAll('files')).toHaveLength(2)
    expect(new Headers(call?.init?.headers).get('Accept')).toBe('application/json')
  })

  it('sends review decisions and job requests as JSON', async () => {
    const { calls } = fakeFetch([
      { method: 'POST', path: /\/api\/review\/item-1$/, body: { id: 'item-1' } },
      { method: 'POST', path: '/api/jobs', body: { id: 'j1' } },
      { path: '/api/reads', body: { items: [], total: 0, limit: 5, offset: 0 } },
    ])
    await api.decide('item-1', { plate: '24830-ب-1' })
    await api.createJob({ kind: 'folder', path: 'batch-01' })
    await api.reads({ limit: 5, status: undefined })
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({ plate: '24830-ب-1' })
    expect(new Headers(calls[1]?.init?.headers).get('Content-Type')).toBe('application/json')
    expect(calls[2]?.url).toBe('/api/reads?limit=5')
  })

  it("reports the service's own explanation", async () => {
    fakeFetch([
      { path: '/api/jobs/x', status: 404, body: { detail: 'No such job.' } },
      {
        method: 'POST',
        path: /review/,
        status: 422,
        body: { detail: [{ msg: "Value error, '1' is not a valid plate under the grammar" }] },
      },
    ])
    await expect(api.job('x')).rejects.toThrow('No such job.')
    const failure = await api.decide('i', { plate: '1' }).catch((e: unknown) => e)
    expect(failure).toBeInstanceOf(ApiError)
    expect((failure as ApiError).status).toBe(422)
    expect(errorMessage(failure)).toBe("'1' is not a valid plate under the grammar")
  })

  it('turns a network failure into a readable error', async () => {
    setFetch(async () => {
      throw new TypeError('Failed to fetch')
    })
    const failure = await api.health().catch((e: unknown) => e)
    expect((failure as ApiError).status).toBe(0)
    expect(errorMessage(failure)).toBe('The plate service cannot be reached.')
    expect(describeError(503, 'not json')).toBe('The plate service answered with status 503.')
    expect(errorMessage('plain')).toBe('plain')
  })

  it('builds service URLs for images and event streams', () => {
    expect(cropUrl('a b', 2)).toBe('/api/reads/a%20b/views/2/crop')
    expect(jobEventsUrl('j1')).toBe('/api/jobs/j1/events')
    expect(serviceUrl('reads/1')).toBe('/api/reads/1')
  })
})
