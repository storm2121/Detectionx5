/**
 * Decoded photo pixels in OpenCV's layout (BGR, 8-bit). `colorSpaceConversion: 'none'`
 * keeps the browser from colour-managing the image, so a PNG decodes to the same samples
 * `cv2.imread` returns. JPEG decoders differ by a level here and there between libraries,
 * which is why the parity fixtures are PNGs.
 */
import type { Pixels } from './image'

export async function decodePng(blob: Blob): Promise<Pixels> {
  const bitmap = await createImageBitmap(blob, {
    colorSpaceConversion: 'none',
    premultiplyAlpha: 'none',
  })
  const { width, height } = bitmap
  const canvas =
    typeof OffscreenCanvas !== 'undefined'
      ? new OffscreenCanvas(width, height)
      : Object.assign(document.createElement('canvas'), { width, height })
  const context = canvas.getContext('2d', { willReadFrequently: true }) as
    | CanvasRenderingContext2D
    | OffscreenCanvasRenderingContext2D
    | null
  if (!context) throw new Error('This browser cannot decode images for the in-browser mode.')
  context.drawImage(bitmap, 0, 0)
  bitmap.close()
  const rgba = context.getImageData(0, 0, width, height).data
  const data = new Uint8Array(width * height * 3)
  for (let i = 0; i < width * height; i += 1) {
    data[3 * i] = rgba[4 * i + 2] as number
    data[3 * i + 1] = rgba[4 * i + 1] as number
    data[3 * i + 2] = rgba[4 * i] as number
  }
  return { width, height, channels: 3, data }
}

export const decodePhoto = decodePng
