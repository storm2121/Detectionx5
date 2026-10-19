/**
 * The recogniser in the browser: plate_reader/crnn/preprocess.py (grey, plain resize to the
 * model input, scale to [-1, 1]) and the post-processing of CRNNRuntime.decode (temperature
 * log-softmax, grammar-constrained beam, posterior over the beam, conformal set).
 */
import type * as ort from 'onnxruntime-web'

import {
  constrainedBeamSearch,
  type Hypothesis,
  logSoftmax,
  posterior,
  predictionSet,
} from './decode'
import { type Pixels, resize, toGrey } from './image'
import type { CRNNMetadataWeb } from './runtime'

export interface ViewRead {
  hypotheses: Hypothesis[]
  prediction: string | null
  confidence: number | null
  predictionSet: string[] | null
}

/** The 8-bit grey model input, exactly as `cv2.cvtColor` and `cv2.resize` produce it. */
export function modelInput(image: Pixels, height = 32, width = 160): Pixels {
  const grey = toGrey(image)
  const shrinking = grey.height > height || grey.width > width
  return resize(grey, width, height, shrinking ? 'area' : 'linear')
}

export function inputTensor(grey: Pixels, mean = 0.5, std = 0.5): Float32Array {
  const out = new Float32Array(grey.data.length)
  const m = Math.fround(mean)
  const s = Math.fround(std)
  for (let i = 0; i < grey.data.length; i += 1) {
    const scaled = Math.fround((grey.data[i] as number) / 255)
    out[i] = Math.fround(Math.fround(scaled - m) / s)
  }
  return out
}

export interface Logits {
  data: Float32Array
  frames: number
  classes: number
}

export async function crnnLogits(
  session: ort.InferenceSession,
  ortModule: typeof ort,
  grey: Pixels,
  metadata: CRNNMetadataWeb,
): Promise<Logits> {
  const { height, width, mean, std } = metadata.input
  const tensor = new ortModule.Tensor('float32', inputTensor(grey, mean, std), [
    1,
    1,
    height,
    width,
  ])
  const name = session.inputNames[0] as string
  const outputs = await session.run({ [name]: tensor })
  const output = outputs[session.outputNames[0] as string] as ort.Tensor
  const [, frames, classes] = output.dims as [number, number, number]
  return { data: output.data as Float32Array, frames, classes }
}

/** CRNNRuntime.decode(logits, "beam", alpha) */
export function decodeBeam(
  logits: Logits,
  metadata: CRNNMetadataWeb,
  alpha: number | null,
): ViewRead {
  const logProbs = logSoftmax(logits.data, logits.frames, logits.classes, metadata.temperature)
  const beam = constrainedBeamSearch(logProbs, logits.frames, logits.classes, metadata.beam_width)
  const dist = posterior(beam)
  const threshold = alpha !== null ? metadata.conformal[String(alpha)] : undefined
  return {
    hypotheses: dist.filter(([, p]) => p > 0).map(([tokens, p]) => ({ tokens, logp: Math.log(p) })),
    prediction: dist[0]?.[0] ?? null,
    confidence: dist[0]?.[1] ?? null,
    predictionSet: threshold !== undefined ? predictionSet(beam, threshold) : null,
  }
}

/** The threshold calibrated for the largest calibrated view count not above `views`. */
export function thresholdFor(
  metadata: CRNNMetadataWeb,
  alpha: number,
  views: number,
): number | null {
  const table = metadata.conformal_fused ?? {}
  const counts = Object.keys(table)
    .map(Number)
    .filter((k) => k <= Math.max(1, views))
    .sort((a, b) => a - b)
  const largest = counts[counts.length - 1]
  if (largest !== undefined) {
    const threshold = table[String(largest)]?.[String(alpha)]
    if (threshold !== undefined) return threshold
  }
  return metadata.conformal[String(alpha)] ?? null
}

/** `crnn-<version>-T<temperature>`, as CRNNRecognizer.version formats it (Python's `:g`). */
export function modelVersion(metadata: CRNNMetadataWeb): string {
  return `crnn-${metadata.version}-T${Number(metadata.temperature.toPrecision(6))}`
}
