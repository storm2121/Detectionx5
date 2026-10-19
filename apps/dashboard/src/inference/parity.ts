/**
 * The browser runtime against the Python pipeline: every fixture of
 * results/parity_fixtures.json (CRNN crops, and a multi-view street-scene set) is read here
 * from the same PNGs and compared with what Python recorded, within the tolerances the
 * fixtures state. The console shows the outcome as its parity indicator, and the Playwright
 * parity test fails when any fixture is out of tolerance.
 */
import { crnnLogits, decodeBeam, modelInput } from './crnn'
import { decodePng } from './decodeImage'
import { readImages } from './pipeline'
import { loadModels, type Backend, ort } from './runtime'

export const PARITY_BASE = '/runtime/parity'

interface CropFixture {
  image: string
  truth: string
  logits: number[][]
  greedy: string
  beam: [string, number][]
  prediction: string | null
  confidence: number | null
  prediction_set: string[] | null
  input?: string
}

interface SceneView {
  image: string
  detections: number[][]
  crop_box: number[]
  prediction: string | null
  hypotheses: [string, number][]
  prediction_set: string[] | null
  input?: string
}

export interface ParityFixtures {
  model_version: string
  alpha: number
  tolerance: { logits: number; probability: number }
  fixtures: CropFixture[]
  scenes?: {
    alpha: number
    detector_version: string
    tolerance: { box: number; detector_confidence: number; probability: number }
    views: SceneView[]
    fused: {
      prediction: string | null
      confidence: number
      posterior: [string, number][]
      prediction_set: string[] | null
      positions: { index: number; symbol: string; distribution: [string, number][] }[]
    }
  }
}

export interface ParityCheck {
  name: string
  ok: boolean
  detail: string
}

export interface ParityReport {
  backend: Backend
  modelVersion: string
  passed: boolean
  checks: ParityCheck[]
  maxima: {
    inputLevels: number
    logits: number
    probability: number
    box: number
    detectorConfidence: number
  }
  seconds: number
}

function name(path: string): string {
  return path.split('/').pop() ?? path
}

async function png(path: string) {
  const response = await fetch(`${PARITY_BASE}/${name(path)}`)
  if (!response.ok) throw new Error(`missing parity fixture ${name(path)}`)
  return decodePng(await response.blob())
}

function base64Bytes(text: string): Uint8Array {
  const binary = atob(text)
  const out = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i)
  return out
}

function sameList(a: readonly string[] | null, b: readonly string[] | null): boolean {
  const x = a ?? []
  const y = b ?? []
  return x.length === y.length && x.every((v, i) => v === y[i])
}

function maxProbabilityGap(expected: [string, number][], actual: [string, number][]): number {
  const lookup = new Map(actual)
  let gap = 0
  for (const [tokens, p] of expected) gap = Math.max(gap, Math.abs((lookup.get(tokens) ?? 0) - p))
  return gap
}

export async function runParity(backend: Backend = 'wasm'): Promise<ParityReport> {
  const started = performance.now()
  const response = await fetch(`${PARITY_BASE}/parity_fixtures.json`)
  if (!response.ok)
    throw new Error('The parity fixtures are missing (results/parity_fixtures.json).')
  const fixtures = (await response.json()) as ParityFixtures
  const models = await loadModels(backend)
  const checks: ParityCheck[] = []
  const maxima = { inputLevels: 0, logits: 0, probability: 0, box: 0, detectorConfidence: 0 }
  if (models.metadata.version !== fixtures.model_version) {
    checks.push({
      name: 'model version',
      ok: false,
      detail: `the console serves ${models.metadata.version}, the fixtures are for ${fixtures.model_version}`,
    })
  }

  for (const fixture of fixtures.fixtures) {
    const image = await png(fixture.image)
    const input = modelInput(image, models.metadata.input.height, models.metadata.input.width)
    let levels = 0
    if (fixture.input) {
      const expected = base64Bytes(fixture.input)
      for (let i = 0; i < expected.length; i += 1) {
        levels = Math.max(levels, Math.abs((expected[i] as number) - (input.data[i] as number)))
      }
    }
    const logits = await crnnLogits(models.crnn, ort, input, models.metadata)
    let logitGap = 0
    fixture.logits.forEach((row, t) =>
      row.forEach((value, c) => {
        logitGap = Math.max(
          logitGap,
          Math.abs(value - (logits.data[t * logits.classes + c] as number)),
        )
      }),
    )
    const read = decodeBeam(logits, models.metadata, fixtures.alpha)
    const beam: [string, number][] = read.hypotheses.map((h) => [h.tokens, Math.exp(h.logp)])
    const probabilityGap = maxProbabilityGap(fixture.beam, beam)
    const ok =
      levels === 0 &&
      logitGap <= fixtures.tolerance.logits &&
      probabilityGap <= fixtures.tolerance.probability &&
      read.prediction === fixture.prediction &&
      sameList(read.predictionSet, fixture.prediction_set) &&
      sameList(
        beam.map(([t]) => t),
        fixture.beam.map(([t]) => t),
      )
    maxima.inputLevels = Math.max(maxima.inputLevels, levels)
    maxima.logits = Math.max(maxima.logits, logitGap)
    maxima.probability = Math.max(maxima.probability, probabilityGap)
    checks.push({
      name: name(fixture.image),
      ok,
      detail: `input ${levels} grey level(s), logits ${logitGap.toExponential(1)}, probability ${probabilityGap.toExponential(1)}`,
    })
  }

  const scenes = fixtures.scenes
  if (scenes) {
    const images = await Promise.all(scenes.views.map((v) => png(v.image)))
    const result = await readImages(models, images, {
      detect: true,
      alpha: scenes.alpha,
      reviewThreshold: 0.9,
    })
    scenes.views.forEach((expected, i) => {
      const view = result.views[i]
      const raw = view?.raw
      let boxGap = Number.POSITIVE_INFINITY
      let scoreGap = Number.POSITIVE_INFINITY
      if (raw && raw.boxes.length === expected.detections.length) {
        boxGap = 0
        scoreGap = 0
        expected.detections.forEach((row, j) => {
          const box = raw.boxes[j] as number[]
          for (let k = 0; k < 4; k += 1)
            boxGap = Math.max(boxGap, Math.abs((row[k] as number) - (box[k] as number)))
          scoreGap = Math.max(scoreGap, Math.abs((row[4] as number) - (raw.scores[j] as number)))
        })
      }
      const hypotheses: [string, number][] = (view?.read?.hypotheses ?? []).map((h) => [
        h.tokens,
        Math.exp(h.logp),
      ])
      const probabilityGap = maxProbabilityGap(expected.hypotheses, hypotheses)
      const cropBox = view?.detection?.box ?? []
      const ok =
        boxGap <= scenes.tolerance.box &&
        scoreGap <= scenes.tolerance.detector_confidence &&
        sameList(cropBox.map(String), expected.crop_box.map(String)) &&
        (view?.read?.prediction ?? null) === expected.prediction &&
        sameList(view?.read?.predictionSet ?? null, expected.prediction_set) &&
        probabilityGap <= scenes.tolerance.probability
      maxima.box = Math.max(maxima.box, Number.isFinite(boxGap) ? boxGap : 0)
      maxima.detectorConfidence = Math.max(
        maxima.detectorConfidence,
        Number.isFinite(scoreGap) ? scoreGap : 0,
      )
      maxima.probability = Math.max(maxima.probability, probabilityGap)
      checks.push({
        name: `${name(expected.image)} (detector and recogniser)`,
        ok,
        detail: `boxes ${boxGap.toExponential(1)} px, scores ${scoreGap.toExponential(1)}, probability ${probabilityGap.toExponential(1)}`,
      })
    })
    const fused = result.fused
    const fusedGap = maxProbabilityGap(scenes.fused.posterior, fused.posterior)
    const positionsOk =
      fused.positions.length === scenes.fused.positions.length &&
      fused.positions.every((p, i) => p.symbol === scenes.fused.positions[i]?.symbol)
    const ok =
      fused.prediction === scenes.fused.prediction &&
      Math.abs(fused.confidence - scenes.fused.confidence) <= scenes.tolerance.probability &&
      fusedGap <= scenes.tolerance.probability &&
      positionsOk &&
      sameList(fused.predictionSet, scenes.fused.prediction_set)
    maxima.probability = Math.max(maxima.probability, fusedGap)
    checks.push({
      name: 'fused read of the scene set',
      ok,
      detail: `posterior ${fusedGap.toExponential(1)}, ${fused.positions.length} characters`,
    })
  }

  return {
    backend: models.backend,
    modelVersion: models.metadata.version,
    passed: checks.every((c) => c.ok),
    checks,
    maxima,
    seconds: (performance.now() - started) / 1000,
  }
}
