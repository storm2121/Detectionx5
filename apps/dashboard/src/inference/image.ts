/**
 * Pixel operations that reproduce OpenCV bit for bit, because the CRNN and the detector
 * must see exactly the pixels the Python pipeline gives them (ARCHITECTURE §13):
 *
 * - `toGrey`: `cv2.cvtColor(BGR2GRAY)` on 8-bit images (15-bit fixed point).
 * - `resize`: `cv2.resize` with INTER_LINEAR (11-bit fixed-point coefficients and the
 *   rounding of OpenCV's SIMD vertical pass) and INTER_AREA (exact block averages for
 *   integer factors, float area weights otherwise, and OpenCV's area-flavoured bilinear
 *   weights when one side grows), for one or three channels.
 *
 * `tests/fixtures/web/resize_cases.json`, written by OpenCV, is the reference the unit tests
 * compare against byte for byte.
 */

export interface Pixels {
  width: number
  height: number
  channels: 1 | 3
  /** Interleaved 8-bit samples (BGR for colour images, as OpenCV stores them). */
  data: Uint8Array
}

const COEF_BITS = 11
const COEF_SCALE = 1 << COEF_BITS
const f32 = Math.fround

/** OpenCV's cvRound: round half to even (and never a negative zero). */
export function cvRound(x: number): number {
  const r = Math.abs(x % 1) === 0.5 ? 2 * Math.round(x / 2) : Math.round(x)
  return r === 0 ? 0 : r
}

/** Python's round() on floats: also half to even. */
export const pyRound = cvRound

function saturateU8(x: number): number {
  return x < 0 ? 0 : x > 255 ? 255 : x
}

function saturateShort(x: number): number {
  return x < -32768 ? -32768 : x > 32767 ? 32767 : x
}

export function toGrey(image: Pixels): Pixels {
  if (image.channels === 1) return image
  const { width, height, data } = image
  const out = new Uint8Array(width * height)
  for (let i = 0; i < width * height; i += 1) {
    const b = data[3 * i] as number
    const g = data[3 * i + 1] as number
    const r = data[3 * i + 2] as number
    out[i] = (b * 3735 + g * 19235 + r * 9798 + (1 << 14)) >> 15
  }
  return { width, height, channels: 1, data: out }
}

export function crop(image: Pixels, box: readonly [number, number, number, number]): Pixels {
  const [x1, y1, x2, y2] = box
  const width = x2 - x1
  const height = y2 - y1
  const cn = image.channels
  const out = new Uint8Array(width * height * cn)
  for (let y = 0; y < height; y += 1) {
    const from = ((y1 + y) * image.width + x1) * cn
    out.set(image.data.subarray(from, from + width * cn), y * width * cn)
  }
  return { width, height, channels: cn, data: out }
}

export type Interpolation = 'linear' | 'area'

/** `cv2.resize(image, (width, height), interpolation=...)` for 8-bit images. */
export function resize(
  src: Pixels,
  width: number,
  height: number,
  interpolation: Interpolation,
): Pixels {
  if (width === src.width && height === src.height) {
    return { ...src, data: src.data.slice() }
  }
  const invScaleX = width / src.width
  const invScaleY = height / src.height
  const scaleX = 1 / invScaleX
  const scaleY = 1 / invScaleY
  const iscaleX = cvRound(scaleX)
  const iscaleY = cvRound(scaleY)
  const areaFast =
    Math.abs(scaleX - iscaleX) < Number.EPSILON && Math.abs(scaleY - iscaleY) < Number.EPSILON
  let mode = interpolation
  // OpenCV: halving both sides with INTER_LINEAR is computed by the exact 2x2 average.
  if (mode === 'linear' && areaFast && iscaleX === 2 && iscaleY === 2) mode = 'area'
  if (mode === 'area' && scaleX >= 1 && scaleY >= 1) {
    return areaFast
      ? resizeAreaFast(src, width, height, iscaleX, iscaleY)
      : resizeArea(src, width, height, scaleX, scaleY)
  }
  return resizeLinear(src, width, height, scaleX, scaleY, invScaleX, invScaleY, mode === 'area')
}

function resizeAreaFast(src: Pixels, dw: number, dh: number, sx: number, sy: number): Pixels {
  const cn = src.channels
  const out = new Uint8Array(dw * dh * cn)
  const area = sx * sy
  const scale = f32(1 / area)
  const rowStride = src.width * cn
  for (let dy = 0; dy < dh; dy += 1) {
    const y0 = dy * sy
    for (let dx = 0; dx < dw; dx += 1) {
      for (let k = 0; k < cn; k += 1) {
        let sum = 0
        for (let yy = 0; yy < sy; yy += 1) {
          const row = (y0 + yy) * rowStride
          for (let xx = 0; xx < sx; xx += 1)
            sum += src.data[row + (dx * sx + xx) * cn + k] as number
        }
        out[(dy * dw + dx) * cn + k] =
          sx === 2 && sy === 2 ? (sum + 2) >> 2 : saturateU8(cvRound(f32(sum * scale)))
      }
    }
  }
  return { width: dw, height: dh, channels: cn, data: out }
}

interface AreaTap {
  di: number
  si: number
  alpha: number
}

function areaTable(ssize: number, dsize: number, scale: number): AreaTap[] {
  const taps: AreaTap[] = []
  for (let dx = 0; dx < dsize; dx += 1) {
    const fsx1 = dx * scale
    const fsx2 = fsx1 + scale
    const cellWidth = Math.min(scale, ssize - fsx1)
    let sx1 = Math.ceil(fsx1)
    let sx2 = Math.floor(fsx2)
    sx2 = Math.min(sx2, ssize - 1)
    sx1 = Math.min(sx1, sx2)
    if (sx1 - fsx1 > 1e-3) taps.push({ di: dx, si: sx1 - 1, alpha: f32((sx1 - fsx1) / cellWidth) })
    for (let sx = sx1; sx < sx2; sx += 1) taps.push({ di: dx, si: sx, alpha: f32(1 / cellWidth) })
    if (fsx2 - sx2 > 1e-3) {
      taps.push({
        di: dx,
        si: sx2,
        alpha: f32(Math.min(Math.min(fsx2 - sx2, 1), cellWidth) / cellWidth),
      })
    }
  }
  return taps
}

function resizeArea(src: Pixels, dw: number, dh: number, scaleX: number, scaleY: number): Pixels {
  const cn = src.channels
  const xtab = areaTable(src.width, dw, scaleX)
  const ytab = areaTable(src.height, dh, scaleY)
  const width = dw * cn
  const out = new Uint8Array(width * dh)
  const buf = new Float32Array(width)
  const sum = new Float32Array(width)
  let prevDy = ytab[0]?.di ?? 0
  const flush = (dy: number) => {
    for (let x = 0; x < width; x += 1) out[dy * width + x] = saturateU8(cvRound(sum[x] as number))
  }
  for (const { di: dy, si: sy, alpha: beta } of ytab) {
    buf.fill(0)
    const row = sy * src.width * cn
    for (const { di, si, alpha } of xtab) {
      for (let k = 0; k < cn; k += 1) {
        const value = src.data[row + si * cn + k] as number
        buf[di * cn + k] = f32((buf[di * cn + k] as number) + f32(value * alpha))
      }
    }
    if (dy !== prevDy) {
      flush(prevDy)
      for (let x = 0; x < width; x += 1) sum[x] = f32(beta * (buf[x] as number))
      prevDy = dy
    } else {
      for (let x = 0; x < width; x += 1)
        sum[x] = f32((sum[x] as number) + f32(beta * (buf[x] as number)))
    }
  }
  flush(prevDy)
  return { width: dw, height: dh, channels: cn, data: out }
}

function linearCoefficients(
  dsize: number,
  ssize: number,
  scale: number,
  invScale: number,
  areaMode: boolean,
  clampEdges: boolean,
): { offsets: Int32Array; alphas: Int16Array; firstClamped: number } {
  const offsets = new Int32Array(dsize)
  const alphas = new Int16Array(dsize * 2)
  let firstClamped = dsize
  for (let d = 0; d < dsize; d += 1) {
    let s: number
    let f: number
    if (!areaMode) {
      f = f32((d + 0.5) * scale - 0.5)
      s = Math.floor(f)
      f = f32(f - s)
    } else {
      s = Math.floor(d * scale)
      f = f32(d + 1 - (s + 1) * invScale)
      f = f <= 0 ? 0 : f32(f - Math.floor(f))
    }
    // Columns are clamped here (OpenCV resets the weight at the edges); rows keep their raw
    // weights and are clamped when the neighbouring rows are fetched.
    if (clampEdges) {
      if (s < 0) {
        f = 0
        s = 0
      }
      if (s + 1 >= ssize) {
        firstClamped = Math.min(firstClamped, d)
        if (s >= ssize - 1) {
          f = 0
          s = ssize - 1
        }
      }
    }
    offsets[d] = s
    alphas[2 * d] = saturateShort(cvRound(f32(f32(1 - f) * COEF_SCALE)))
    alphas[2 * d + 1] = saturateShort(cvRound(f32(f * COEF_SCALE)))
  }
  return { offsets, alphas, firstClamped }
}

/**
 * OpenCV's vertical pass for 8-bit output, with the rounding of its SIMD kernel
 * (`((S0 >> 4) * b0 >> 16) + ((S1 >> 4) * b1 >> 16) + 2) >> 2`), which OpenCV applies to every
 * pixel of the row: the reference cases include widths that are not a multiple of the
 * vector width.
 */
function verticalPass(
  s0: Int32Array,
  s1: Int32Array,
  b0: number,
  b1: number,
  width: number,
  dst: Uint8Array,
  offset: number,
) {
  const simd = (x: number) => {
    const a = ((s0[x] as number) >> 4) * b0
    const b = ((s1[x] as number) >> 4) * b1
    return saturateU8(((a >> 16) + (b >> 16) + 2) >> 2)
  }
  for (let x = 0; x < width; x += 1) dst[offset + x] = simd(x)
}

function resizeLinear(
  src: Pixels,
  dw: number,
  dh: number,
  scaleX: number,
  scaleY: number,
  invScaleX: number,
  invScaleY: number,
  areaMode: boolean,
): Pixels {
  const cn = src.channels
  const xs = linearCoefficients(dw, src.width, scaleX, invScaleX, areaMode, true)
  const ys = linearCoefficients(dh, src.height, scaleY, invScaleY, areaMode, false)
  const width = dw * cn
  const out = new Uint8Array(width * dh)
  const rowCache = new Map<number, Int32Array>()
  const horizontal = (sy: number): Int32Array => {
    const cached = rowCache.get(sy)
    if (cached) return cached
    const row = new Int32Array(width)
    const base = sy * src.width * cn
    for (let dx = 0; dx < dw; dx += 1) {
      const sx = xs.offsets[dx] as number
      for (let k = 0; k < cn; k += 1) {
        const a = src.data[base + sx * cn + k] as number
        if (dx < xs.firstClamped) {
          const b = src.data[base + (sx + 1) * cn + k] as number
          row[dx * cn + k] =
            a * (xs.alphas[2 * dx] as number) + b * (xs.alphas[2 * dx + 1] as number)
        } else {
          row[dx * cn + k] = a * COEF_SCALE
        }
      }
    }
    if (rowCache.size > 4) rowCache.clear()
    rowCache.set(sy, row)
    return row
  }
  for (let dy = 0; dy < dh; dy += 1) {
    const sy = ys.offsets[dy] as number
    // The vertical neighbours are clamped to the image, as OpenCV does.
    const r0 = Math.min(Math.max(sy, 0), src.height - 1)
    const r1 = Math.min(Math.max(sy + 1, 0), src.height - 1)
    verticalPass(
      horizontal(r0),
      horizontal(r1),
      ys.alphas[2 * dy] as number,
      ys.alphas[2 * dy + 1] as number,
      width,
      out,
      dy * width,
    )
  }
  return { width: dw, height: dh, channels: cn, data: out }
}
