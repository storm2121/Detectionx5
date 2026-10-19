/**
 * The whole read in the browser, mirroring plate_reader.pipeline.PlatePipeline and the
 * service's review rule: detect each photo's plate, read it with the constrained beam, fuse
 * the views, attach the conformal set for the number of views that proposed a plate, and
 * decide whether a person should review it. The result has the service's `ReadOut` shape,
 * so the Read page draws a browser read with the same components.
 */
import type { Candidate, ReadOut, ViewOut } from '@/api/types'

import {
  crnnLogits,
  decodeBeam,
  modelInput,
  modelVersion,
  thresholdFor,
  type ViewRead,
} from './crnn'
import { type Detection, detectionsFromBoxes, rawBoxes, type RawBoxes } from './detector'
import { type Fused, probabilisticFusion } from './fusion'
import { fieldsOf, formatOf, toDisplay } from './grammar'
import type { Pixels } from './image'
import { type Models, ort } from './runtime'

export interface BrowserView {
  index: number
  raw: RawBoxes | null
  detection: Detection | null
  input: Pixels | null
  read: ViewRead | null
}

export interface BrowserRead {
  read: ReadOut
  views: BrowserView[]
  /** The fused read in canonical tokens (the ReadOut carries display spellings). */
  fused: Fused
  /** Crop images for the view cards (data URLs), by view. */
  crops: (string | null)[]
  stageMs: Record<string, number>
}

export interface ReadOptions {
  detect: boolean
  alpha: number
  reviewThreshold: number
  reviewEmptySets?: boolean
}

let counter = 0

export function reviewReason(
  prediction: string | null,
  predictionSet: string[] | null,
  confidence: number,
  threshold: number,
  anyView: boolean,
  reviewEmptySets = true,
): string | null {
  if (prediction === null) return anyView ? 'unreadable' : null
  if (predictionSet !== null) {
    if (predictionSet.length > 1) return 'set_size'
    if (predictionSet.length === 0 && reviewEmptySets) return 'empty_set'
  }
  if (confidence < threshold) return 'low_confidence'
  return null
}

function candidates(pairs: [string, number][]): Candidate[] {
  return pairs.map(([tokens, probability]) => ({ plate: toDisplay(tokens), tokens, probability }))
}

export function pixelsToDataUrl(image: Pixels): string | null {
  if (typeof document === 'undefined') return null
  const canvas = document.createElement('canvas')
  canvas.width = image.width
  canvas.height = image.height
  const context = canvas.getContext('2d')
  if (!context) return null
  const rgba = context.createImageData(image.width, image.height)
  for (let i = 0; i < image.width * image.height; i += 1) {
    const grey = image.channels === 1
    rgba.data[4 * i] = image.data[grey ? i : 3 * i + 2] as number
    rgba.data[4 * i + 1] = image.data[grey ? i : 3 * i + 1] as number
    rgba.data[4 * i + 2] = image.data[grey ? i : 3 * i] as number
    rgba.data[4 * i + 3] = 255
  }
  context.putImageData(rgba, 0, 0)
  return canvas.toDataURL('image/png')
}

export async function readImages(
  models: Models,
  images: Pixels[],
  options: ReadOptions,
): Promise<BrowserRead> {
  const start = performance.now()
  const stageMs: Record<string, number> = { detect: 0, recognise: 0, fuse: 0 }
  const views: BrowserView[] = []
  for (const [index, image] of images.entries()) {
    let tick = performance.now()
    let raw: RawBoxes | null = null
    let detections: Detection[]
    if (options.detect) {
      raw = await rawBoxes(models.detector, ort, image)
      detections = detectionsFromBoxes(image, raw)
    } else {
      detections = [{ box: [0, 0, image.width, image.height], confidence: 1, crop: image }]
    }
    stageMs.detect = (stageMs.detect ?? 0) + performance.now() - tick
    const best = detections[0] ?? null
    if (!best) {
      views.push({ index, raw, detection: null, input: null, read: null })
      continue
    }
    tick = performance.now()
    const input = modelInput(best.crop, models.metadata.input.height, models.metadata.input.width)
    const logits = await crnnLogits(models.crnn, ort, input, models.metadata)
    const read = decodeBeam(logits, models.metadata, options.alpha)
    stageMs.recognise = (stageMs.recognise ?? 0) + performance.now() - tick
    views.push({ index, raw, detection: best, input, read })
  }

  const tick = performance.now()
  const readable = views.filter((v) => v.read !== null)
  const proposing = readable.filter((v) => (v.read?.hypotheses.length ?? 0) > 0).length
  const threshold = thresholdFor(models.metadata, options.alpha, proposing)
  const fused = probabilisticFusion(
    readable.map((v) => ({ hypotheses: v.read?.hypotheses ?? [] })),
    readable.map(() => 1),
    threshold,
  )
  stageMs.fuse = performance.now() - tick

  const prediction = fused.prediction
  const reason = reviewReason(
    prediction,
    fused.predictionSet,
    fused.confidence,
    options.reviewThreshold,
    readable.length > 0,
    options.reviewEmptySets ?? true,
  )
  counter += 1
  const viewOut: ViewOut[] = views.map((view) => ({
    index: view.index,
    box: view.detection ? view.detection.box : null,
    detector_confidence: view.detection ? view.detection.confidence : null,
    weight: view.read ? 1 : 0,
    prediction: view.read?.prediction ? toDisplay(view.read.prediction) : null,
    confidence: view.read?.confidence ?? null,
    hypotheses: candidates((view.read?.hypotheses ?? []).map((h) => [h.tokens, Math.exp(h.logp)])),
    prediction_set: view.read?.predictionSet?.length
      ? view.read.predictionSet.map(toDisplay)
      : null,
  }))
  const read: ReadOut = {
    id: `browser-${counter}`,
    created_at: new Date().toISOString(),
    plate: prediction ? toDisplay(prediction) : null,
    tokens: prediction,
    format: prediction ? formatOf(prediction) : null,
    fields: prediction ? fieldsOf(prediction) : null,
    confidence: fused.confidence,
    calibrated: models.metadata.calibrated ?? true,
    prediction_set: fused.predictionSet ? fused.predictionSet.map(toDisplay) : null,
    level: fused.predictionSet ? Math.round((1 - options.alpha) * 1e6) / 1e6 : null,
    fusion: 'probabilistic',
    model_version: modelVersion(models.metadata),
    review: { queued: reason !== null, reason, item_id: null },
    views: viewOut,
    posterior: candidates(fused.posterior),
    positions: fused.positions.map((p) => ({
      index: p.index,
      symbol: p.symbol,
      confidence: p.distribution.find(([s]) => s === p.symbol)?.[1] ?? 0,
      distribution: p.distribution.map(([symbol, probability]) => ({ symbol, probability })),
    })),
    latency_ms: performance.now() - start,
    status: reason ? 'queued' : 'accepted',
    source: 'browser',
  }
  return {
    read,
    views,
    fused,
    crops: views.map((v) => (v.detection ? pixelsToDataUrl(v.detection.crop) : null)),
    stageMs,
  }
}
