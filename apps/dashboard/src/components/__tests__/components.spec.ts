import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import { ACCEPTED, QUEUED, plugins } from '@/__tests__/helpers'
import type { EvalResult } from '@/api/results'
import type { Photo } from '@/stores/read'
import evaluation from '@results/eval_synthetic.json'
import real from '@results/eval_data.json'

import CalibrationCurve from '../CalibrationCurve.vue'
import ConfidenceBar from '../ConfidenceBar.vue'
import ConfusionMatrix from '../ConfusionMatrix.vue'
import FusionTable from '../FusionTable.vue'
import MetricTable from '../MetricTable.vue'
import PhotoThumb from '../PhotoThumb.vue'
import PhotoTray from '../PhotoTray.vue'
import PlateReadout from '../PlateReadout.vue'
import PredictionSet from '../PredictionSet.vue'
import SimToRealGap from '../SimToRealGap.vue'
import SyntheticNote from '../SyntheticNote.vue'
import DisclosureSection from '../ui/DisclosureSection.vue'
import SegmentedControl from '../ui/SegmentedControl.vue'
import SwitchField from '../ui/SwitchField.vue'
import TextField from '../ui/TextField.vue'
import ViewCard from '../ViewCard.vue'

const EVAL = evaluation as unknown as EvalResult
const REAL = real as unknown as EvalResult
let global: { plugins: ReturnType<typeof plugins>['list'] }

beforeEach(() => {
  global = { plugins: plugins().list }
})

describe('the plate readout', () => {
  it('shows each field and one outlined confidence cell per character, aligned to the plate', () => {
    const wrapper = mount(PlateReadout, {
      props: {
        positions: ACCEPTED.positions,
        fields: ACCEPTED.fields,
        format: ACCEPTED.format,
        plate: ACCEPTED.plate,
      },
      global,
    })
    expect(wrapper.get('[data-field="digits"]').text()).toBe(ACCEPTED.fields?.digits)
    expect(wrapper.get('[data-field="letter"]').text()).toBe(ACCEPTED.fields?.letter)
    expect(wrapper.get('[data-field="region"]').text()).toBe(ACCEPTED.fields?.region)
    expect(wrapper.get('[role="img"]').attributes('aria-label')).toContain('Standard plate')
    const characters = ACCEPTED.positions.filter((p) => p.symbol !== '-')
    expect(wrapper.findAll('.winner')).toHaveLength(characters.length)
    // the plate and the heatmap share one column template, so the cells sit under the glyphs
    const columns = (style: string | undefined) =>
      /grid-template-columns: ([^;]+)/.exec(style ?? '')?.[1]
    const plate = wrapper.get('.plate').attributes('style')
    const heat = wrapper.get('[data-testid="character-heatmap"]').attributes('style')
    expect(columns(plate)).toBeTruthy()
    expect(columns(plate)).toBe(columns(heat))
    expect(wrapper.findAll('table tbody tr')).toHaveLength(ACCEPTED.positions.length)
  })

  it('shows the WW mark of a temporary plate, and a read without a plate', () => {
    const temporary = mount(PlateReadout, {
      props: {
        positions: ['7', '2', '-', 'W', 'W'].map((symbol, index) => ({
          index,
          symbol,
          confidence: 0.9,
          distribution: [{ symbol, probability: 0.9 }],
        })),
        fields: { digits: '72', letter: null, region: null },
        format: 'temporary',
        plate: '72 WW',
      },
      global,
    })
    expect(temporary.get('[data-field="mark"]').text()).toBe('WW')
    expect(temporary.text()).toContain('Temporary')
    const none = mount(PlateReadout, {
      props: { positions: [], fields: null, format: null, plate: null },
      global,
    })
    expect(none.text()).toContain('No plate read')
  })
})

describe('confidence and the prediction set', () => {
  it('reports a calibrated posterior without claiming certainty, and says when it is low', () => {
    const wrapper = mount(ConfidenceBar, {
      props: { value: ACCEPTED.confidence, threshold: 0.9, calibrated: true },
    })
    expect(wrapper.text()).toContain('>99.9%')
    expect(wrapper.text()).toContain('Reads under 90% go to review')
    expect(wrapper.text()).toContain('synthetic results are not real-world accuracy')
    const low = mount(ConfidenceBar, { props: { value: 0.4, threshold: 0.9, calibrated: false } })
    expect(low.text()).toContain('under the review threshold')
    expect(low.text()).toContain('Not calibrated')
  })

  it('distinguishes one, several, empty and no set', () => {
    const one = mount(PredictionSet, {
      props: { set: ['27-د-9'], level: 0.95, prediction: '27-د-9' },
    })
    expect(one.attributes('data-state')).toBe('single')
    expect(one.text()).toContain('certified at 95%')
    const several = mount(PredictionSet, {
      props: { set: ['27-د-9', '22-د-9'], level: 0.9, prediction: '27-د-9' },
    })
    expect(several.findAll('li')).toHaveLength(2)
    expect(several.text()).toContain('2 plates remain possible at 90%')
    const empty = mount(PredictionSet, { props: { set: [], level: 0.95, prediction: null } })
    expect(empty.text()).toContain('Empty set')
    expect(empty.text()).toContain('goes to review')
    const none = mount(PredictionSet, { props: { set: null, level: null, prediction: null } })
    expect(none.attributes('data-state')).toBe('none')
  })
})

describe('read details', () => {
  it('tabulates every candidate across the views, in the order the tray shows them', () => {
    const wrapper = mount(FusionTable, { props: { read: ACCEPTED } })
    const header = wrapper.findAll('thead th').map((th) => th.text())
    expect(header).toEqual(['Candidate', 'View 1', 'View 2', 'View 3', 'Fused', 'Set'])
    const rows = wrapper.findAll('tbody tr')
    expect(rows[0]?.classes()).toContain('top')
    expect(rows[0]?.text()).toContain('in set')
    // the first view proposed nothing: moved to the end, its dash moves with it
    const moved = mount(FusionTable, { props: { read: ACCEPTED, order: [1, 2, 0] } })
    const cells = moved.findAll('tbody tr')[0]?.findAll('td') ?? []
    expect(cells[2]?.text()).toBe('–')
  })

  it('summarises one view and its hypotheses', () => {
    const view = ACCEPTED.views[1]!
    const wrapper = mount(ViewCard, { props: { view, readId: ACCEPTED.id, number: 2 }, global })
    expect(wrapper.text()).toContain('View 2')
    expect(wrapper.findAll('.hyps li').length).toBeGreaterThan(0)
    expect(wrapper.get('img.crop').attributes('src')).toBe(`/api/reads/${ACCEPTED.id}/views/1/crop`)
    const abstained = mount(ViewCard, {
      props: { view: ACCEPTED.views[0]!, readId: ACCEPTED.id },
      global,
    })
    expect(abstained.text()).toContain('No plate found')
    const boxless = mount(ViewCard, {
      props: { view: { ...ACCEPTED.views[0]!, box: null }, readId: ACCEPTED.id },
      global,
    })
    expect(boxless.find('img.crop').exists()).toBe(false)
  })

  it('overlays the detected box in photo pixels', async () => {
    const wrapper = mount(PhotoThumb, {
      props: { src: 'data:image/png;base64,', alt: 'Photo 1', box: [10, 20, 110, 60] },
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

  it('reorders the tray from the keyboard and announces the new position', async () => {
    const photos: Photo[] = ['a.png', 'b.png'].map((name, i) => ({
      id: `p${i}`,
      file: new File([], name, { type: 'image/png' }),
      url: '',
      width: null,
      height: null,
      view: null,
    }))
    const wrapper = mount(PhotoTray, { props: { photos }, global, attachTo: document.body })
    const items = wrapper.findAll('li.item')
    expect(items[0]?.attributes('aria-label')).toBe('View 1, a.png')
    await items[0]!.trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()
    expect(wrapper.emitted('move')?.[0]).toEqual([0, 1])
    expect(wrapper.text()).toContain('Moved to position 2 of 2.')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Remove')!
      .trigger('click')
    expect(wrapper.emitted('remove')?.[0]).toEqual(['p0'])
    wrapper.unmount()
  })
})

describe('controls', () => {
  it('a segmented control is a radio group the arrow keys move through', async () => {
    const wrapper = mount(SegmentedControl, {
      props: {
        modelValue: 'server',
        label: 'Where the plate is read',
        options: [
          { label: 'Server', value: 'server' },
          { label: 'In this browser', value: 'browser' },
        ],
      },
      attachTo: document.body,
    })
    expect(wrapper.get('[role="radiogroup"]').attributes('aria-label')).toBe(
      'Where the plate is read',
    )
    const radios = wrapper.findAll('[role="radio"]')
    expect(radios[0]?.attributes('aria-checked')).toBe('true')
    expect(radios[1]?.attributes('tabindex')).toBe('-1')
    await radios[0]!.trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['browser'])
    wrapper.unmount()
  })

  it('a switch has the switch role, its label as its name, and toggles', async () => {
    const wrapper = mount(SwitchField, {
      props: { modelValue: true, label: 'Find the plate in each photo', hint: 'A hint.' },
    })
    const control = wrapper.get('[role="switch"]')
    expect(control.attributes('aria-checked')).toBe('true')
    const labelId = control.attributes('aria-labelledby')
    expect(wrapper.get(`[id="${labelId}"]`).text()).toBe('Find the plate in each photo')
    await control.trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('a text field ties its hint and its inline error to the input', () => {
    const wrapper = mount(TextField, {
      props: {
        modelValue: '24',
        label: 'Correct plate',
        hint: 'A hint.',
        error: 'Not a plate yet.',
      },
    })
    const input = wrapper.get('input')
    expect(input.attributes('aria-invalid')).toBe('true')
    expect((input.attributes('aria-describedby') ?? '').split(' ')).toHaveLength(2)
    expect(wrapper.get('[role="alert"]').text()).toBe('Not a plate yet.')
  })

  it('a disclosure keeps its content in the document and opens it in place', async () => {
    const wrapper = mount(DisclosureSection, {
      props: { title: 'Views and hypotheses', summary: '3 of 3 views read' },
      slots: { default: '<p class="inside">content</p>' },
    })
    const button = wrapper.get('button')
    expect(button.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('.inside').exists()).toBe(true)
    expect(wrapper.get('.content').attributes('hidden')).toBeDefined()
    await button.trigger('click')
    await flushPromises()
    expect(button.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.content').attributes('hidden')).toBeUndefined()
  })
})

describe('results views', () => {
  const beam = EVAL.recognizers['crnn-beam']!

  it('draws one point per filled reliability bin', () => {
    const wrapper = mount(CalibrationCurve, {
      props: { bins: beam.reliability, ece: beam.metrics.ece?.value ?? null },
      attachTo: document.body,
    })
    const filled = beam.reliability.filter((b) => b.n > 0).length
    expect(wrapper.findAll('.points circle')).toHaveLength(filled)
    expect(wrapper.text()).toContain('Expected calibration error')
    wrapper.unmount()
  })

  it('writes the counts into the confusion matrix and outlines the diagonal', () => {
    const wrapper = mount(ConfusionMatrix, { props: { confusion: beam.letter_confusion }, global })
    expect(wrapper.findAll('td.diagonal')).toHaveLength(beam.letter_confusion.rows.length)
    const first = beam.letter_confusion.matrix[0]?.[0]
    expect(wrapper.find('td.diagonal .count').text()).toBe(String(first))
  })

  it('shows every metric with its interval in words', () => {
    const columns = Object.fromEntries(
      Object.entries(REAL.recognizers).map(([name, r]) => [name, r.metrics]),
    )
    const wrapper = mount(MetricTable, {
      props: { columns, metrics: ['exact_match', 'cer', 'coverage'], caption: 'Real', digits: 0 },
    })
    expect(wrapper.findAll('tbody tr')).toHaveLength(3)
    const exact = REAL.recognizers['crnn-beam']!.metrics.exact_match!
    const words = `${Math.round(exact.value * 100)}% (${Math.round(exact.ci_low * 100)} to ${Math.round(exact.ci_high * 100)})`
    expect(wrapper.text()).toContain(words)
    expect(wrapper.text()).toContain('lower is better')
  })

  it('puts synthetic and real side by side with n, and draws two bars per recogniser', () => {
    const wrapper = mount(SimToRealGap, {
      props: { synthetic: EVAL, real: REAL },
      attachTo: document.body,
    })
    expect(wrapper.text()).toContain(`Synthetic test set (n = ${EVAL.set.n})`)
    expect(wrapper.text()).toContain(`Real plates (n = ${REAL.set.n})`)
    expect(wrapper.text()).toContain('points lower on real photos')
    expect(wrapper.findAll('g.bar')).toHaveLength(Object.keys(REAL.recognizers).length * 2)
    wrapper.unmount()
  })

  it('always carries the synthetic label', () => {
    const wrapper = mount(SyntheticNote, { props: { detail: 'Calibrated on synthetic plates.' } })
    expect(wrapper.text()).toContain('Synthetic results are not real-world accuracy.')
    expect(wrapper.text()).toContain('Calibrated on synthetic plates.')
  })

  it('reads the queued example as a single crop', () => {
    expect(QUEUED.views).toHaveLength(1)
    expect(QUEUED.review.queued).toBe(true)
  })
})
