/**
 * ONNX Runtime Web sessions for the detector and the CRNN, loaded from the console's own
 * static files (`/runtime/models/...`, copied from models/ at build time) so that a photo read in the
 * browser never leaves the device. WebGPU is used when the browser offers an adapter;
 * otherwise, and always for the parity check, the WebAssembly backend runs on the CPU.
 */
import * as ort from 'onnxruntime-web'

export type Backend = 'webgpu' | 'wasm'

export interface CRNNMetadataWeb {
  version: string
  charset: string[]
  charset_id: string
  input: { height: number; width: number; channels: number; mean: number; std: number }
  temperature: number
  beam_width: number
  calibrated?: boolean
  conformal: Record<string, number>
  conformal_fused?: Record<string, Record<string, number>>
}

export interface Models {
  backend: Backend
  crnn: ort.InferenceSession
  detector: ort.InferenceSession
  metadata: CRNNMetadataWeb
  detectorVersion: string | null
}

// Not /models: that is a page of the console, and a folder of the same name would shadow it.
export const MODEL_BASE = '/runtime/models'

let configured = false

function configure() {
  if (configured) return
  // The WebAssembly binary is bundled by Vite next to the code that loads it. Threads need
  // cross-origin isolation, which a static nginx page does not have.
  ort.env.wasm.numThreads = 1
  ort.env.logLevel = 'error'
  configured = true
}

export async function webgpuAvailable(): Promise<boolean> {
  const gpu = (navigator as Navigator & { gpu?: { requestAdapter(): Promise<unknown> } }).gpu
  if (!gpu) return false
  try {
    return Boolean(await gpu.requestAdapter())
  } catch {
    return false
  }
}

async function session(url: string, backend: Backend): Promise<ort.InferenceSession> {
  configure()
  return ort.InferenceSession.create(url, {
    executionProviders: backend === 'webgpu' ? ['webgpu', 'wasm'] : ['wasm'],
    graphOptimizationLevel: 'all',
  })
}

const cache = new Map<Backend, Promise<Models>>()

/** Load both models once per backend. */
export function loadModels(backend: Backend): Promise<Models> {
  let pending = cache.get(backend)
  if (!pending) {
    pending = (async () => {
      const response = await fetch(`${MODEL_BASE}/crnn.json`)
      if (!response.ok) throw new Error('The CRNN metadata is missing (models/crnn.json).')
      const metadata = (await response.json()) as CRNNMetadataWeb
      const [crnn, detector] = await Promise.all([
        session(`${MODEL_BASE}/crnn.onnx`, backend),
        session(`${MODEL_BASE}/detector.onnx`, backend),
      ])
      let detectorVersion: string | null = null
      try {
        const versions = await fetch(`${MODEL_BASE}/versions.json`)
        if (versions.ok)
          detectorVersion = ((await versions.json()) as { detector?: string }).detector ?? null
      } catch {
        detectorVersion = null
      }
      return { backend, crnn, detector, metadata, detectorVersion }
    })()
    cache.set(backend, pending)
    pending.catch(() => cache.delete(backend))
  }
  return pending
}

export { ort }
