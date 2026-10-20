import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import App from '@/App.vue'
import { ACCEPTED, fakeFetch, plugins, png, QUEUED } from '@/__tests__/helpers'
import { setFetch } from '@/api/client'
import calibration from '@results/calibration_crnn.json'
import fused from '@results/calibration_fused.json'
import real from '@results/eval_data.json'
import endToEnd from '@results/eval_data_e2e.json'
import detectorReal from '@results/eval_detector_data.json'
import detectorEval from '@results/eval_detector_synthetic.json'
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
  { path: '/api/review/summary', body: { pending: 1, ready_to_export: 1 } },
  { path: '/api/models', body: MODELS },
  { path: '/api/reads', body: { items: [], total: 0, limit: 8, offset: 0 } },
  {
    path: '/api/results',
    body: [
      'eval_synthetic',
      'calibration_crnn',
      'calibration_fused',
      'train_crnn',
      'eval_detector_synthetic',
      'eval_detector_data',
      'eval_data',
      'eval_data_e2e',
    ].map((name) => ({
      name,
      schema: null,
      label: 'synthetic results are not real-world accuracy',
    })),
  },
  { path: '/api/results/eval_synthetic', body: evaluation },
  { path: '/api/results/calibration_crnn', body: calibration },
  { path: '/api/results/calibration_fused', body: fused },
  { path: '/api/results/train_crnn', body: training },
  { path: '/api/results/eval_detector_synthetic', body: detectorEval },
  { path: '/api/results/eval_data', body: real },
  { path: '/api/results/eval_data_e2e', body: endToEnd },
  { path: '/api/results/eval_detector_data', body: detectorReal },
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
    expect(wrapper.text()).toContain('Accepted')
    expect(wrapper.text().toLowerCase()).toContain('synthetic results are not real-world accuracy')
    // the navigation names the review queue with what waits in it
    expect(wrapper.text()).toContain('Review queue (1 waiting)')
    wrapper.unmount()
  })

  it('reads only photos the viewer adds: no synthetic sample path', async () => {
    const { wrapper } = await visit('/read')
    expect(wrapper.find('[data-testid="samples-button"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('synthetic photos')
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
    // the real photos come first: what the set is, from the box and end to end side by side
    const section = wrapper.get('[data-testid="real-photos"]')
    const card = real.set.card
    expect(section.text()).toContain(`${card.photos} photos holding ${card.boxes} labelled plates`)
    expect(section.text()).toContain(`one of ${card.camera_photos} camera photos`)
    expect(section.get('[data-testid="detector-overlap"]').text()).toContain(
      'The detector has seen these scenes.',
    )
    expect(section.text()).toContain(`resample the ${real.bootstrap.groups} vehicle groups`)
    expect(section.get('[data-testid="real-labelled"]').text()).toContain(
      `${real.set.n} plates in ${real.set.photos} photos`,
    )
    const whole = section.get('[data-testid="real-end-to-end"]').text()
    expect(whole).toContain(`${endToEnd.set.n} photos, the labelled boxes ignored`)
    const summary = section.get('[data-testid="detection-summary"]').text()
    expect(summary).toContain(
      endToEnd.detection.no_detection ? 'had no detection' : 'Every photo had a detection',
    )
    expect(summary).toContain('lay on the labelled plate in')
    const detector = section.get('[data-testid="detector-comparison"]').text()
    expect(detector).toContain(`Street photos (n = ${detectorReal.counts.images} photos`)
    expect(detector).toContain(`Synthetic street scenes (n = ${detectorEval.counts.images} scenes)`)
    expect(detector).toContain('Synthetic results are not real-world accuracy.')
    expect(section.get('[data-testid="calibration-note"]').text()).toContain(
      'The calibration remains synthetic',
    )
    expect(section.text()).toContain('a separate real calibration split comes next')
    const first = wrapper.findAll('h2').map((h) => h.text())
    expect(first.indexOf('Real photos')).toBeLessThan(
      first.indexOf('Development and synthetic harness'),
    )
    wrapper.unmount()
  })

  it('lists the active models, the registry and the training curve', async () => {
    const { wrapper } = await visit('/models')
    await flushPromises()
    expect(wrapper.get('[data-testid="model-version"]').text()).toBe('crnn-test')
    expect(wrapper.find('[data-testid="registry-table"]').text()).toContain('Active')
    const gap = wrapper.get('[data-testid="sim-to-real"]').text()
    expect(gap).toContain(`Real plates (n = ${real.set.n})`)
    expect(gap).toContain('points lower on real photos')
    expect(wrapper.find('[data-testid="training-curve"]').exists()).toBe(true)
    const detector = wrapper.get('[data-testid="detector-eval"]').text()
    expect(detector).toContain(detectorEval.metrics.map50.toFixed(3))
    expect(detector).toContain('mAP@50-95')
    const onPhotos = wrapper.get('[data-testid="detector-eval-real"]').text()
    expect(onPhotos).toContain(detectorReal.metrics.map50.toFixed(3))
    expect(onPhotos).toContain(`${detectorReal.counts.images} photos holding`)
    expect(onPhotos).toContain('Not an independent measurement')
    expect(wrapper.get('[data-testid="detector-card"]').text()).toContain(
      'Synthetic results are not real-world accuracy.',
    )
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
    expect(wrapper.get('[data-testid="decided"]').text()).toContain('Corrected')
    expect(wrapper.get('[data-testid="export-button"]').text()).toBe('Export 1 correction')
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
    expect(wrapper.text()).toContain('Queue one to start.')
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
