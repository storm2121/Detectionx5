import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import App from '@/App.vue'
import { ACCEPTED, fakeFetch, plugins, png, QUEUED } from '@/__tests__/helpers'
import { setFetch } from '@/api/client'
import calibration from '@results/calibration_crnn.json'
import fused from '@results/calibration_fused.json'
import evaluation from '@results/eval_synthetic.json'
import training from '@results/train_crnn.json'
import { useReadStore } from '@/stores/read'

const MODELS = {
  recognizer: {
    name: 'crnn-beam',
    version: 'crnn-test',
    metadata: {
      version: 'test',
      charset: ['', '0'],
      charset_id: 'abc',
      input: { height: 32, width: 160, channels: 1, mean: 0.5, std: 0.5 },
      temperature: 0.9,
      beam_width: 10,
      conformal: { '0.05': 0.002, '0.1': 0.001 },
      conformal_fused: { '1': { '0.05': 0.003 }, '3': { '0.05': 7e-10 } },
    },
  },
  detector: { available: true, path: 'detector.onnx' },
  fusion: 'probabilistic',
  alpha: 0.05,
  review_threshold: 0.9,
  registry: {
    models: [{ kind: 'crnn', version: 'v1', file: 'crnn.onnx', bytes: 2048 }],
    active: { crnn: 'v1' },
  },
}

const HEALTH = {
  status: 'ok',
  database: 'ok',
  queue: 'ok',
  model_version: 'crnn-test',
  detector: true,
}

const common = [
  { path: '/api/health', body: HEALTH },
  { path: '/api/models', body: MODELS },
  { path: '/api/reads', body: { items: [], total: 0, limit: 8, offset: 0 } },
  {
    path: '/api/results',
    body: ['eval_synthetic', 'calibration_crnn', 'calibration_fused', 'train_crnn'].map((name) => ({
      name,
      schema: null,
      label: 'synthetic results are not real-world accuracy',
    })),
  },
  { path: '/api/results/eval_synthetic', body: evaluation },
  { path: '/api/results/calibration_crnn', body: calibration },
  { path: '/api/results/calibration_fused', body: fused },
  { path: '/api/results/train_crnn', body: training },
]

afterEach(() => setFetch(null))

async function visit(path: string, extra: Parameters<typeof fakeFetch>[0] = []) {
  const fetcher = fakeFetch([...extra, ...common])
  const { list, router } = plugins()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: list }, attachTo: document.body })
  await flushPromises()
  await flushPromises()
  return { wrapper, router, fetcher }
}

describe('the console', () => {
  it('reads photos and shows the plate, its set, the views and the heatmap', async () => {
    const { wrapper, fetcher } = await visit('/read', [
      { method: 'POST', path: '/api/read', body: ACCEPTED },
    ])
    expect(wrapper.get('h1').text()).toBe('Read a plate')
    expect(wrapper.text()).toContain('Service ready')
    const store = useReadStore()
    store.add([png('a.png'), png('b.png'), png('c.png'), new File(['x'], 'notes.txt')])
    await flushPromises()
    expect(store.photos).toHaveLength(3)
    expect(store.rejected).toBe(1)
    await wrapper.get('[data-testid="read-button"]').trigger('click')
    await flushPromises()
    const posted = fetcher.calls.find((c) => c.init?.method === 'POST')
    expect(posted?.url).toBe('/api/read?detect=true')
    expect(wrapper.get('[data-field="digits"]').text()).toBe(ACCEPTED.fields?.digits)
    expect(wrapper.get('[data-testid="conformal-set"]').text()).toContain(ACCEPTED.plate ?? '')
    expect(wrapper.findAll('[data-testid="view-card"]')).toHaveLength(3)
    expect(wrapper.find('[data-testid="character-heatmap"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('accepted')
    expect(wrapper.text()).toContain('Synthetic results are not real-world accuracy.')
    wrapper.unmount()
  })

  it('shows why a stored read went to review', async () => {
    const { wrapper } = await visit(`/reads/${QUEUED.id}`, [
      { path: `/api/reads/${QUEUED.id}`, body: QUEUED },
    ])
    expect(wrapper.get('h1').text()).toBe('Stored read')
    expect(wrapper.text()).toContain('review: empty conformal set')
    expect(wrapper.text()).toContain('Empty set')
    wrapper.unmount()
  })

  it('explains a failed read', async () => {
    const { wrapper } = await visit('/read', [
      {
        method: 'POST',
        path: '/api/read',
        status: 413,
        body: { detail: 'Upload at most 10 photos per request.' },
      },
    ])
    useReadStore().add([png()])
    await flushPromises()
    await wrapper.get('[data-testid="read-button"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="error-note"]').text()).toContain('Upload at most 10 photos')
    wrapper.unmount()
  })

  it('renders the evaluation from the committed results', async () => {
    const { wrapper } = await visit('/evaluation')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('Evaluation')
    expect(wrapper.find('[data-testid="metric-table"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="calibration-curve"]').length).toBeGreaterThanOrEqual(3)
    expect(wrapper.find('[data-testid="confusion-matrix"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="fusion-comparison"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="coverage-table"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('Synthetic results are not real-world accuracy.')
    wrapper.unmount()
  })

  it('lists the active models, the registry and the training curve', async () => {
    const { wrapper } = await visit('/models')
    await flushPromises()
    expect(wrapper.get('[data-testid="model-version"]').text()).toBe('crnn-test')
    expect(wrapper.find('[data-testid="registry-table"]').text()).toContain('active')
    expect(wrapper.find('[data-testid="training-curve"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('typesets the methods', async () => {
    const { wrapper } = await visit('/methods')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="math"]').length).toBeGreaterThan(8)
    expect(wrapper.find('.katex').exists()).toBe(true)
    wrapper.unmount()
  })

  it('corrects a queued read and exports the reviewed crops', async () => {
    const item = {
      id: 'item-1',
      read_id: QUEUED.id,
      created_at: QUEUED.created_at,
      reason: 'empty_set',
      status: 'pending',
      plate: QUEUED.plate,
      confidence: QUEUED.confidence,
      prediction_set: [],
      corrected_plate: null,
      crops: [`/reads/${QUEUED.id}/views/0/crop`],
    }
    const { wrapper, fetcher } = await visit('/review', [
      { path: '/api/review/queue', body: [item] },
      {
        method: 'POST',
        path: '/api/review/item-1',
        body: { ...item, status: 'reviewed', corrected_plate: '27-د-9' },
      },
      {
        method: 'POST',
        path: '/api/review/export',
        body: { id: 'e1', exported: 1, path: '/data/ocr/train/labels.csv', files: [] },
      },
    ])
    expect(wrapper.findAll('[data-testid="review-item"]')).toHaveLength(1)
    await wrapper.get('[data-testid="save-correction"]').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Type the plate as it reads')
    await wrapper.get('[data-testid="correction-input"]').setValue('27-د-9')
    await wrapper.get('form.decide').trigger('submit')
    await flushPromises()
    const decision = fetcher.calls.find((c) => c.url.endsWith('/api/review/item-1'))
    expect(JSON.parse(String(decision?.init?.body))).toEqual({ plate: '27-د-9' })
    expect(wrapper.findAll('[data-testid="review-item"]')).toHaveLength(0)
    expect(wrapper.get('[data-testid="decided"]').text()).toContain('corrected')
    await wrapper.get('[data-testid="export-button"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="export-result"]').text()).toContain('Exported 1 crop')
    wrapper.unmount()
  })

  it('reports a job the service refuses', async () => {
    const { wrapper } = await visit('/jobs', [
      { path: '/api/jobs', body: [] },
      {
        method: 'POST',
        path: '/api/jobs',
        status: 404,
        body: { detail: 'No such folder under the jobs root.' },
      },
    ])
    expect(wrapper.text()).toContain('No jobs yet.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Give a path under the jobs root')
    await wrapper.get('#job-path').setValue('missing')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('No such folder under the jobs root.')
    wrapper.unmount()
  })

  it('switches between light and dark themes', async () => {
    const { wrapper } = await visit('/methods')
    const before = document.documentElement.classList.contains('dx-dark')
    await wrapper.get('[data-testid="theme-toggle"]').trigger('click')
    await flushPromises()
    expect(document.documentElement.classList.contains('dx-dark')).toBe(!before)
    expect(document.documentElement.dataset.theme).toBe(before ? 'light' : 'dark')
    wrapper.unmount()
  })
})
