/**
 * The plate detector in the browser: Ultralytics' letterbox (minimum rectangle, as the
 * dynamic-shape export expects), the NMS-free YOLOv10 head, and the padding, cropping and
 * de-duplication of plate_reader/detector.py and detector_onnx.py.
 */
import type * as ort from 'onnxruntime-web'

import { crop, type Pixels, pyRound, resize } from './image'

export const DETECTOR_SIZE = 640
export const STRIDE = 32
export const PAD_VALUE = 114
export const CONFIDENCE = 0.25
export const CROP_PADDING = 0.08
export const DUPLICATE_IOU = 0.6

export type Box = [number, number, number, number]

export interface Detection {
  /** The padded integer box the crop was taken from. */
  box: Box
  confidence: number
  crop: Pixels
}

export interface Letterboxed {
  image: Pixels
  scale: number
  left: number
  top: number
}

/** Resize keeping aspect so the long side is `size`, then pad to the stride (auto). */
export function letterbox(
  image: Pixels,
  size = DETECTOR_SIZE,
  auto = true,
  stride = STRIDE,
): Letterboxed {
  const { width: w, height: h } = image
  const scale = Math.min(size / h, size / w)
  const newW = pyRound(w * scale)
  const newH = pyRound(h * scale)
  let dw = size - newW
  let dh = size - newH
  if (auto) {
    dw %= stride
    dh %= stride
  }
  const halfW = dw / 2
  const halfH = dh / 2
  const resized = newW === w && newH === h ? image : resize(image, newW, newH, 'linear')
  const top = pyRound(halfH - 0.1)
  const bottom = pyRound(halfH + 0.1)
  const left = pyRound(halfW - 0.1)
  const right = pyRound(halfW + 0.1)
  const width = newW + left + right
  const height = newH + top + bottom
  const cn = image.channels
  const data = new Uint8Array(width * height * cn).fill(PAD_VALUE)
  for (let y = 0; y < newH; y += 1) {
    const from = y * newW * cn
    data.set(resized.data.subarray(from, from + newW * cn), ((y + top) * width + left) * cn)
  }
  return { image: { width, height, channels: cn, data }, scale, left, top }
}

/** NCHW float32 RGB in [0, 1] from a BGR letterboxed image. */
export function detectorTensor(image: Pixels): Float32Array {
  const plane = image.width * image.height
  const out = new Float32Array(3 * plane)
  for (let i = 0; i < plane; i += 1) {
    out[i] = Math.fround((image.data[3 * i + 2] as number) / 255)
    out[plane + i] = Math.fround((image.data[3 * i + 1] as number) / 255)
    out[2 * plane + i] = Math.fround((image.data[3 * i] as number) / 255)
  }
  return out
}

export function padBox(box: readonly number[], width: number, height: number): Box {
  const [x1, y1, x2, y2] = box as [number, number, number, number]
  const padX = (x2 - x1) * CROP_PADDING
  const padY = (y2 - y1) * CROP_PADDING
  return [
    Math.max(0, Math.trunc(x1 - padX)),
    Math.max(0, Math.trunc(y1 - padY)),
    Math.min(width, Math.trunc(x2 + padX)),
    Math.min(height, Math.trunc(y2 + padY)),
  ]
}

export function iou(a: Box, b: Box): number {
  const ix1 = Math.max(a[0], b[0])
  const iy1 = Math.max(a[1], b[1])
  const ix2 = Math.min(a[2], b[2])
  const iy2 = Math.min(a[3], b[3])
  const inter = Math.max(0, ix2 - ix1) * Math.max(0, iy2 - iy1)
  if (inter === 0) return 0
  const union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
  return union ? inter / union : 0
}

export function deduplicate(detections: Detection[]): Detection[] {
  const kept: Detection[] = []
  const ordered = [...detections].sort((a, b) => b.confidence - a.confidence)
  for (const candidate of ordered) {
    if (kept.every((k) => iou(candidate.box, k.box) < DUPLICATE_IOU)) kept.push(candidate)
  }
  return kept
}

export interface RawBoxes {
  boxes: [number, number, number, number][]
  scores: number[]
}

/** Boxes over the confidence threshold in image coordinates, before padding. */
export async function rawBoxes(
  session: ort.InferenceSession,
  ortModule: typeof ort,
  image: Pixels,
  confidence = CONFIDENCE,
): Promise<RawBoxes> {
  const boxed = letterbox(image)
  const input = new ortModule.Tensor('float32', detectorTensor(boxed.image), [
    1,
    3,
    boxed.image.height,
    boxed.image.width,
  ])
  const name = session.inputNames[0] as string
  const outputs = await session.run({ [name]: input })
  const output = outputs[session.outputNames[0] as string] as ort.Tensor
  const values = output.data as Float32Array
  const rows = (output.dims[1] as number) ?? 0
  const width = (output.dims[2] as number) ?? 6
  const boxes: [number, number, number, number][] = []
  const scores: number[] = []
  const clip = (v: number, hi: number) => Math.min(Math.max(v, 0), hi)
  for (let r = 0; r < rows; r += 1) {
    const score = values[r * width + 4] as number
    if (!(score >= confidence)) continue
    const at = (k: number) => values[r * width + k] as number
    boxes.push([
      clip((at(0) - boxed.left) / boxed.scale, image.width),
      clip((at(1) - boxed.top) / boxed.scale, image.height),
      clip((at(2) - boxed.left) / boxed.scale, image.width),
      clip((at(3) - boxed.top) / boxed.scale, image.height),
    ])
    scores.push(score)
  }
  return { boxes, scores }
}

export function detectionsFromBoxes(image: Pixels, raw: RawBoxes): Detection[] {
  const detections: Detection[] = []
  raw.boxes.forEach((box, i) => {
    const padded = padBox(box, image.width, image.height)
    if (padded[2] <= padded[0] || padded[3] <= padded[1]) return
    detections.push({ box: padded, confidence: raw.scores[i] as number, crop: crop(image, padded) })
  })
  return deduplicate(detections)
}
