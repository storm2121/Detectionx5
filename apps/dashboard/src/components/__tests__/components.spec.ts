import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import { ACCEPTED, QUEUED, plugins } from '@/__tests__/helpers'
import type { EvalResult } from '@/api/results'
import evaluation from '@results/eval_synthetic.json'

import CalibrationCurve from '../CalibrationCurve.vue'
import CharacterHeatmap from '../CharacterHeatmap.vue'
import ConfidenceMeter from '../ConfidenceMeter.vue'
import ConformalSet from '../ConformalSet.vue'
import ConfusionMatrix from '../ConfusionMatrix.vue'
import FusionTable from '../FusionTable.vue'
import MetricTable from '../MetricTable.vue'
import PhotoFrame from '../PhotoFrame.vue'
import PlateFields from '../PlateFields.vue'
import SyntheticNote from '../SyntheticNote.vue'
import ViewCard from '../ViewCard.vue'

const EVAL = evaluation as unknown as EvalResult
let global: { plugins: ReturnType<typeof plugins>['list'] }

beforeEach(() => {
  global = { plugins: plugins().list }
})

describe('plate fields', () => {
  it('shows digits, letter and region of a standard plate', () => {
    const wrapper = mount(PlateFields, {
      props: { fields: ACCEPTED.fields, format: ACCEPTED.format, plate: ACCEPTED.plate },
    })
    expect(wrapper.get('[data-field="digits"]').text()).toBe(ACCEPTED.fields?.digits)
    expect(wrapper.get('[data-field="letter"]').text()).toBe(ACCEPTED.fields?.letter)
    expect(wrapper.get('[data-field="region"]').text()).toBe(ACCEPTED.fields?.region)
    expect(wrapper.get('[role="img"]').attributes('aria-label')).toContain('Standard plate')
  })

  it('shows the WW mark of a temporary plate, and an unread plate', () => {
    const temporary = mount(PlateFields, {
      props: {
        fields: { digits: '72173', letter: null, region: null },
        format: 'temporary',
        plate: '72173 WW',
      },
    })
    expect(temporary.get('[data-field="mark"]').text()).toBe('WW')
    expect(temporary.find('[data-field="letter"]').exists()).toBe(false)
    const none = mount(PlateFields, { props: { fields: null, format: null, plate: null } })
    expect(none.text()).toContain('No plate read')
  })
})

describe('conformal set', () => {
  it('distinguishes one, several, empty and no set', () => {
    const one = mount(ConformalSet, {
      props: { set: ['27-د-9'], level: 0.95, prediction: '27-د-9' },
    })
    expect(one.attributes('data-state')).toBe('single')
    expect(one.text()).toContain('certified at 95%')
    const several = mount(ConformalSet, {
      props: { set: ['27-د-9', '22-د-9'], level: 0.9, prediction: '27-د-9' },
    })
    expect(several.findAll('li')).toHaveLength(2)
    expect(several.text()).toContain('2 plates remain possible at 90%')
    const empty = mount(ConformalSet, { props: { set: [], level: 0.95, prediction: null } })
    expect(empty.text()).toContain('Empty set')
    expect(empty.text()).toContain('goes to review')
    const none = mount(ConformalSet, { props: { set: null, level: null, prediction: null } })
    expect(none.attributes('data-state')).toBe('none')
  })
})

describe('confidence meter', () => {
  it('reports a calibrated posterior without claiming certainty', () => {
    const wrapper = mount(ConfidenceMeter, {
      props: { value: ACCEPTED.confidence, threshold: 0.9, calibrated: true },
    })
    expect(wrapper.text()).toContain('>99.9%')
    expect(wrapper.text()).toContain('review below 90%')
    const low = mount(ConfidenceMeter, { props: { value: 0.4, threshold: 0.9, calibrated: false } })
    expect(low.find('.fill.low').exists()).toBe(true)
    expect(low.text()).toContain('Not calibrated')
  })
})

describe('read details', () => {
  it('tabulates every candidate across the views', () => {
    const wrapper = mount(FusionTable, { props: { read: ACCEPTED } })
    const header = wrapper.findAll('thead th').map((th) => th.text())
    expect(header).toEqual(['Candidate', 'View 1', 'View 2', 'View 3', 'Fused', 'In set'])
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThan(1)
    expect(rows[0]?.classes()).toContain('top')
    expect(rows[0]?.text()).toContain('in set')
  })

  it('draws one outlined cell per character and an accessible table', () => {
    const wrapper = mount(CharacterHeatmap, { props: { positions: ACCEPTED.positions }, global })
    const characters = ACCEPTED.positions.filter((p) => p.symbol !== '-')
    expect(wrapper.findAll('rect.winner')).toHaveLength(characters.length)
    expect(wrapper.findAll('table tbody tr')).toHaveLength(ACCEPTED.positions.length)
    expect(wrapper.get('svg').attributes('role')).toBe('img')
    expect(wrapper.get('desc').text()).toContain('>99.9%')
  })

  it('summarises one view and its hypotheses', () => {
    const view = ACCEPTED.views[1]!
    const wrapper = mount(ViewCard, { props: { view, readId: ACCEPTED.id }, global })
    expect(wrapper.text()).toContain('View 2')
    expect(wrapper.findAll('.hyps li').length).toBeGreaterThan(0)
    expect(wrapper.get('img.crop').attributes('src')).toBe(`/api/reads/${ACCEPTED.id}/views/1/crop`)
    const abstained = mount(ViewCard, {
      props: { view: ACCEPTED.views[0]!, readId: ACCEPTED.id },
      global,
    })
    expect(abstained.text()).toContain('no plate found')
    expect(abstained.find('img.crop').exists()).toBe(false)
  })

  it('overlays the detected box in photo pixels', async () => {
    const wrapper = mount(PhotoFrame, {
      props: {
        src: 'data:image/png;base64,',
        alt: 'Photo 1',
        box: [10, 20, 110, 60],
        badge: 'View 1',
      },
    })
    expect(wrapper.find('[data-testid="plate-box"]').exists()).toBe(false)
    const image = wrapper.get('img')
    Object.defineProperty(image.element, 'naturalWidth', { value: 640 })
    Object.defineProperty(image.element, 'naturalHeight', { value: 480 })
    await image.trigger('load')
    const overlay = wrapper.get('[data-testid="plate-box"]')
    expect(overlay.attributes('viewBox')).toBe('0 0 640 480')
    expect(overlay.findAll('rect')[1]?.attributes('width')).toBe('100')
    expect(wrapper.emitted('measure')?.[0]).toEqual([640, 480])
  })

  it('reads the queued example as a single crop', () => {
    expect(QUEUED.views).toHaveLength(1)
    expect(QUEUED.review.queued).toBe(true)
  })
})

describe('evaluation views', () => {
  const beam = EVAL.recognizers['crnn-beam']!

  it('draws a bar per filled reliability bin', () => {
    const wrapper = mount(CalibrationCurve, {
      props: { bins: beam.reliability, ece: beam.metrics.ece?.value ?? null },
    })
    const filled = beam.reliability.filter((b) => b.n > 0).length
    expect(wrapper.findAll('rect.bar')).toHaveLength(filled)
    expect(wrapper.text()).toContain('Expected calibration error')
  })

  it('colours the confusion matrix with the counts written in', () => {
    const wrapper = mount(ConfusionMatrix, { props: { confusion: beam.letter_confusion }, global })
    expect(wrapper.findAll('td.diagonal')).toHaveLength(beam.letter_confusion.rows.length)
    const first = beam.letter_confusion.matrix[0]?.[0]
    expect(wrapper.find('td.diagonal').text()).toBe(String(first))
  })

  it('shows every metric with its bootstrap interval', () => {
    const columns = Object.fromEntries(
      Object.entries(EVAL.recognizers).map(([name, r]) => [name, r.metrics]),
    )
    const wrapper = mount(MetricTable, {
      props: { columns, metrics: ['exact_match', 'cer', 'coverage'], caption: 'Synthetic' },
    })
    expect(wrapper.findAll('tbody tr')).toHaveLength(3)
    expect(wrapper.text()).toContain('95% CI')
    expect(wrapper.text()).toContain('lower is better')
  })

  it('always carries the synthetic label', () => {
    const wrapper = mount(SyntheticNote, { props: { detail: 'Calibrated on synthetic plates.' } })
    expect(wrapper.text()).toContain('Synthetic results are not real-world accuracy.')
    expect(wrapper.text()).toContain('Calibrated on synthetic plates.')
  })
})
