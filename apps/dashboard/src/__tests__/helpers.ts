import { createPinia, setActivePinia, type Pinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { vi } from 'vitest'
import type { Plugin } from 'vue'
import { createMemoryHistory, type Router } from 'vue-router'

import { setFetch } from '@/api/client'
import type { ReadOut } from '@/api/types'
import accepted from '@/fixtures/read-accepted.json'
import queued from '@/fixtures/read-queued.json'
import { makeRouter } from '@/router'

export const ACCEPTED = accepted as unknown as ReadOut
export const QUEUED = queued as unknown as ReadOut

export interface Route {
  method?: string
  path: RegExp | string
  status?: number
  body: unknown
}

/** A fetch double answering the given routes; records every request. */
export function fakeFetch(routes: Route[]) {
  const calls: { url: string; init: RequestInit | undefined }[] = []
  const impl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    calls.push({ url, init })
    const method = (init?.method ?? 'GET').toUpperCase()
    const route = routes.find(
      (r) =>
        (r.method ?? 'GET').toUpperCase() === method &&
        (typeof r.path === 'string' ? url.split('?')[0] === r.path : r.path.test(url)),
    )
    if (!route)
      return new Response(JSON.stringify({ detail: `no route for ${url}` }), { status: 404 })
    return new Response(JSON.stringify(route.body), {
      status: route.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  setFetch(impl as unknown as typeof fetch)
  return { impl, calls }
}

export function plugins(): { pinia: Pinia; router: Router; list: Plugin[] } {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = makeRouter(createMemoryHistory())
  return {
    pinia,
    router,
    list: [pinia, router, [PrimeVue, { theme: 'none' }] as unknown as Plugin],
  }
}

export function png(name = 'photo.png'): File {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}
