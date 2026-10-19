import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { constrainedBeamSearch, logSoftmax, posterior, predictionSet } from '../decode'
import { fsum } from '../fsum'
import { align, perPositionPosterior, probabilisticFusion } from '../fusion'
import { accepts, fieldsOf, formatOf, toDisplay } from '../grammar'
import { cvRound, type Pixels, resize, toGrey } from '../image'
import { letterbox, padBox } from '../detector'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..', '..', '..', '..', '..')
const read = <T>(path: string) => JSON.parse(readFileSync(join(repo, path), 'utf-8')) as T

function bytes(text: string): Uint8Array {
  return new Uint8Array(Buffer.from(text, 'base64'))
}

interface Cases {
  resize: {
    source: [number, number, number]
    target: [number, number]
    interpolation: 'linear' | 'area'
    src: string
    expected: string
  }[]
  grey: { size: [number, number]; src: string; expected: string }
}

const CASES = read<Cases>('tests/fixtures/web/opencv_cases.json')

interface CropFixture {
  image: string
  truth: string
  logits: number[][]
  greedy: string
  beam: [string, number][]
  prediction: string | null
  confidence: number | null
  prediction_set: string[] | null
}

const PARITY = read<{
  temperature: number
  beam_width: number
  alpha: number
  tolerance: { logits: number; probability: number }
  fixtures: CropFixture[]
  scenes: {
    views: { hypotheses: [string, number][] }[]
    fused: {
      prediction: string
      confidence: number
      posterior: [string, number][]
      positions: { symbol: string; distribution: [string, number][] }[]
    }
  }
}>('results/parity_fixtures.json')

const METADATA = read<{ conformal: Record<string, number> }>('models/crnn.json')

describe('OpenCV pixel operations', () => {
  it('rounds half to even like cvRound and Python', () => {
    expect([0.5, 1.5, 2.5, 3.5, -1.5, 2.4, 2.6].map(cvRound)).toEqual([0, 2, 2, 4, -2, 2, 3])
  })

  it('converts BGR to grey exactly', () => {
    const [w, h] = CASES.grey.size
    const src: Pixels = { width: w, height: h, channels: 3, data: bytes(CASES.grey.src) }
    expect(Buffer.from(toGrey(src).data).toString('base64')).toBe(CASES.grey.expected)
  })

  for (const c of CASES.resize) {
    const [sw, sh, cn] = c.source
    const [dw, dh] = c.target
    it(`resizes ${sw}x${sh}x${cn} to ${dw}x${dh} (${c.interpolation}) byte for byte`, () => {
      const src: Pixels = { width: sw, height: sh, channels: cn as 1 | 3, data: bytes(c.src) }
      const out = resize(src, dw, dh, c.interpolation)
      const expected = bytes(c.expected)
      let worst = 0
      for (let i = 0; i < expected.length; i += 1) {
        worst = Math.max(worst, Math.abs((out.data[i] as number) - (expected[i] as number)))
      }
      expect(worst).toBe(0)
    })
  }

  it('letterboxes to the stride and pads boxes like the Python detector', () => {
    const image: Pixels = {
      width: 640,
      height: 480,
      channels: 3,
      data: new Uint8Array(640 * 480 * 3),
    }
    const boxed = letterbox(image)
    expect([boxed.image.width, boxed.image.height, boxed.left, boxed.top, boxed.scale]).toEqual([
      640, 480, 0, 0, 1,
    ])
    const odd: Pixels = {
      width: 500,
      height: 375,
      channels: 3,
      data: new Uint8Array(500 * 375 * 3),
    }
    const grown = letterbox(odd)
    expect(grown.image.width % 32).toBe(0)
    expect(grown.image.height % 32).toBe(0)
    expect(padBox([100.4, 50.6, 200.2, 80.9], 640, 480)).toEqual([92, 48, 208, 83])
  })
})

describe('decoding and fusion against the Python fixtures', () => {
  for (const fixture of PARITY.fixtures) {
    it(`reproduces the constrained beam of ${fixture.image.split('/').pop()}`, () => {
      const frames = fixture.logits.length
      const classes = fixture.logits[0]?.length ?? 0
      const flat = Float32Array.from(fixture.logits.flat())
      const logProbs = logSoftmax(flat, frames, classes, PARITY.temperature)
      const beam = constrainedBeamSearch(logProbs, frames, classes, PARITY.beam_width)
      const dist = posterior(beam)
      expect(dist.map(([t]) => t)).toEqual(fixture.beam.map(([t]) => t))
      dist.forEach(([, p], i) =>
        expect(Math.abs(p - (fixture.beam[i]?.[1] ?? 0))).toBeLessThan(1e-6),
      )
      expect(dist[0]?.[0] ?? null).toBe(fixture.prediction)
      const threshold = METADATA.conformal[String(PARITY.alpha)] as number
      expect(predictionSet(beam, threshold)).toEqual(fixture.prediction_set ?? [])
    })
  }

  it('fuses the scene views exactly as Python does', () => {
    const views = PARITY.scenes.views.map((v) => ({
      hypotheses: v.hypotheses
        .filter(([, p]) => p > 0)
        .map(([tokens, p]) => ({ tokens, logp: Math.log(p) })),
    }))
    const fused = probabilisticFusion(views)
    expect(fused.prediction).toBe(PARITY.scenes.fused.prediction)
    expect(Math.abs(fused.confidence - PARITY.scenes.fused.confidence)).toBeLessThan(1e-6)
    expect(fused.positions.map((p) => p.symbol)).toEqual(
      PARITY.scenes.fused.positions.map((p) => p.symbol),
    )
  })

  it('sums exactly and aligns like strings.align', () => {
    // Reference values from CPython's math.fsum.
    expect(fsum([0.1, 0.2, 0.3, -0.6])).toBe(2.7755575615628914e-17)
    expect(fsum(new Array<number>(10).fill(0.1))).toBe(1)
    expect(fsum([1e100, 1.0, -1e100, 1e-100, 1e50, -1.0, -1e50])).toBe(1e-100)
    expect(fsum([1e-16, 1, 1e16])).toBe(1.0000000000000002e16)
    expect(fsum([2 ** 53, 1, 1e-10])).toBe(9007199254740994)
    expect(align('27-د-9', '227-د-9')).toEqual([
      [null, 0],
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 4],
      [4, 5],
      [5, 6],
    ])
    const positions = perPositionPosterior('1-WW', [1], [new Map([['1-WW', 0]])])
    expect(positions.map((p) => p.symbol)).toEqual(['1', '-', 'W', 'W'])
  })
})

describe('the plate grammar in the browser', () => {
  it('accepts and formats plates like the Python grammar', () => {
    expect(accepts('24830-ب-1')).toBe(true)
    expect(accepts('72173-WW')).toBe(true)
    expect(accepts('24830-ب')).toBe(false)
    expect(formatOf('72173-WW')).toBe('temporary')
    expect(toDisplay('72173-WW')).toBe('72173 WW')
    expect(toDisplay('24830-ب-1')).toBe('24830-ب-1')
    expect(fieldsOf('24830-ب-1')).toEqual({ digits: '24830', letter: 'ب', region: '1' })
    expect(fieldsOf('72173-WW')).toEqual({ digits: '72173', letter: null, region: null })
  })
})
