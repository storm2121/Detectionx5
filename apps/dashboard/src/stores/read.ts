import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'

import { api, errorMessage } from '@/api/client'
import type { ReadOut } from '@/api/types'

export const MAX_PHOTOS = 10

export type ReadMode = 'server' | 'browser'
const MODE_KEY = 'dx-read-mode'

function readMode(): ReadMode {
  try {
    return window.localStorage.getItem(MODE_KEY) === 'browser' ? 'browser' : 'server'
  } catch {
    return 'server'
  }
}

export interface Photo {
  id: string
  file: File
  url: string
  width: number | null
  height: number | null
}

let counter = 0

function objectUrl(file: File): string {
  return typeof URL.createObjectURL === 'function' ? URL.createObjectURL(file) : ''
}

function revoke(url: string): void {
  if (url && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url)
}

/** The Read page's photos and the last read; kept while the viewer visits other pages. */
export const useReadStore = defineStore('read', () => {
  const photos = ref<Photo[]>([])
  const detect = ref(true)
  const status = ref<'idle' | 'reading' | 'done' | 'error'>('idle')
  const error = ref<string | null>(null)
  const result = shallowRef<ReadOut | null>(null)
  const rejected = ref(0)
  const mode = ref<ReadMode>(readMode())
  /** Crop images of an in-browser read (a stored read's crops come from the service). */
  const browserCrops = ref<(string | null)[]>([])

  const canRead = computed(() => photos.value.length > 0 && status.value !== 'reading')

  function add(files: Iterable<File>) {
    let skipped = 0
    for (const file of files) {
      if (!file.type.startsWith('image/')) {
        skipped += 1
        continue
      }
      if (photos.value.length >= MAX_PHOTOS) {
        skipped += 1
        continue
      }
      counter += 1
      photos.value.push({
        id: `p${counter}`,
        file,
        url: objectUrl(file),
        width: null,
        height: null,
      })
    }
    rejected.value = skipped
    if (result.value) {
      result.value = null
      status.value = 'idle'
    }
  }

  function remove(id: string) {
    const index = photos.value.findIndex((p) => p.id === id)
    if (index === -1) return
    const [photo] = photos.value.splice(index, 1)
    if (photo) revoke(photo.url)
    result.value = null
    status.value = 'idle'
  }

  function clear() {
    photos.value.forEach((p) => revoke(p.url))
    photos.value = []
    result.value = null
    error.value = null
    rejected.value = 0
    status.value = 'idle'
  }

  function measured(id: string, width: number, height: number) {
    const photo = photos.value.find((p) => p.id === id)
    if (photo) {
      photo.width = width
      photo.height = height
    }
  }

  function setMode(next: ReadMode) {
    mode.value = next
    result.value = null
    status.value = 'idle'
    try {
      window.localStorage.setItem(MODE_KEY, next)
    } catch {
      // storage blocked: the choice lasts for this page only
    }
  }

  async function read(
    options: { alpha?: number; reviewThreshold?: number; backend?: 'webgpu' | 'wasm' } = {},
  ) {
    if (!canRead.value) return
    status.value = 'reading'
    error.value = null
    try {
      if (mode.value === 'browser') {
        const { readFiles } = await import('@/inference/browserRead')
        const out = await readFiles(
          photos.value.map((p) => p.file),
          {
            backend: options.backend ?? 'wasm',
            detect: detect.value,
            alpha: options.alpha ?? 0.05,
            reviewThreshold: options.reviewThreshold ?? 0.9,
          },
        )
        browserCrops.value = out.crops
        result.value = out.read
      } else {
        browserCrops.value = []
        result.value = await api.read(
          photos.value.map((p) => p.file),
          detect.value,
        )
      }
      status.value = 'done'
    } catch (cause) {
      error.value = errorMessage(cause)
      result.value = null
      status.value = 'error'
    }
  }

  /** The synthetic sample scenes the dashboard ships (copied from tests/fixtures/parity). */
  async function loadSamples(names: readonly string[]) {
    clear()
    const files: File[] = []
    for (const name of names) {
      const response = await fetch(`/samples/${name}`)
      if (!response.ok) throw new Error(`Sample ${name} is missing (run pnpm assets).`)
      files.push(new File([await response.blob()], name, { type: 'image/png' }))
    }
    add(files)
  }

  return {
    photos,
    detect,
    status,
    error,
    result,
    rejected,
    mode,
    browserCrops,
    canRead,
    setMode,
    add,
    remove,
    clear,
    measured,
    read,
    loadSamples,
  }
})
