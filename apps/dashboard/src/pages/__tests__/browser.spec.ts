import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from '@/App.vue'
import { fakeFetch, plugins, png } from '@/__tests__/helpers'
import { setFetch } from '@/api/client'
import { useReadStore } from '@/stores/read'

// The heavy runtime (ONNX Runtime Web) is replaced: these tests cover the page's wiring;
// the runtime itself is covered by src/inference/__tests__ and the Playwright parity test.
vi.mock('@/inference/runtime', () => ({
  webgpuAvailable: async () => false,
  loadModels: async () => ({}),
}))

vi.mock('@/inference/parity', () => ({
  runParity: async () => ({
    backend: 'wasm',
    modelVersion: 'test',
    passed: true,
    checks: [
      { name: 'crnn_00.png', ok: true, detail: '' },
      { name: 'fused read of the scene set', ok: true, detail: '' },
    ],
    maxima: { inputLevels: 0, logits: 0, probability: 0, box: 0, detectorConfidence: 0 },
    seconds: 1,
  }),
}))

vi.mock('@/inference/browserRead', async () => {
  const fixture = (await import('@/fixtures/read-accepted.json')).default
  return {
    readFiles: vi.fn(async () => ({
      read: { ...fixture, id: 'browser-1', source: 'browser' },
      views: [],
      fused: null,
      crops: [null, 'data:image/png;base64,iVBORw0KGgo=', null],
      stageMs: {},
    })),
  }
})

afterEach(() => setFetch(null))

describe('the in-browser mode', () => {
  it('reads on the device, shows the parity indicator and sends no photo', async () => {
    const fetcher = fakeFetch([
      { path: '/api/health', status: 503, body: { detail: 'offline' } },
      { path: '/api/models', status: 503, body: { detail: 'offline' } },
      { path: '/api/reads', status: 503, body: { detail: 'offline' } },
    ])
    const { list, router } = plugins()
    await router.push('/read')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: list }, attachTo: document.body })
    await flushPromises()
    const toggle = wrapper.get('[data-testid="mode-toggle"]')
    const browserButton = toggle.findAll('button').find((b) => b.text() === 'In this browser')
    expect(browserButton).toBeDefined()
    await browserButton!.trigger('click')
    await flushPromises()
    await flushPromises()
    expect(wrapper.get('[data-testid="parity-indicator"]').text()).toContain(
      'parity with Python: 2 of 2 fixtures',
    )
    const store = useReadStore()
    expect(store.mode).toBe('browser')
    store.add([png('a.png'), png('b.png'), png('c.png')])
    await flushPromises()
    await wrapper.get('[data-testid="read-button"]').trigger('click')
    await flushPromises()
    await flushPromises()
    expect(wrapper.text()).toContain('read in this browser, not stored')
    expect(wrapper.findAll('[data-testid="view-card"]')).toHaveLength(3)
    expect(fetcher.calls.some((c) => c.init?.method === 'POST')).toBe(false)
    const { readFiles } = await import('@/inference/browserRead')
    expect(readFiles).toHaveBeenCalledOnce()
    expect(vi.mocked(readFiles).mock.calls[0]?.[1]).toMatchObject({
      backend: 'wasm',
      detect: true,
      alpha: 0.05,
      reviewThreshold: 0.9,
    })
    // Back to the server: the choice is remembered.
    const serverButton = toggle.findAll('button').find((b) => b.text() === 'Server')
    await serverButton!.trigger('click')
    expect(store.mode).toBe('server')
    wrapper.unmount()
  })
})
