/**
 * The Read page's entry point into the in-browser runtime: decode the dropped photos and
 * run the pipeline on the backend the console chose. Loaded on demand, so ONNX Runtime Web
 * is only downloaded by viewers who switch to the in-browser mode.
 */
import { decodePhoto } from './decodeImage'
import { type BrowserRead, readImages } from './pipeline'
import { type Backend, loadModels } from './runtime'

export interface BrowserReadOptions {
  backend: Backend
  detect: boolean
  alpha: number
  reviewThreshold: number
}

export async function readFiles(
  files: readonly File[],
  options: BrowserReadOptions,
): Promise<BrowserRead> {
  const models = await loadModels(options.backend)
  const images = await Promise.all(files.map((file) => decodePhoto(file)))
  return readImages(models, images, {
    detect: options.detect,
    alpha: options.alpha,
    reviewThreshold: options.reviewThreshold,
  })
}
