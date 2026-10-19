import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

import { errorMessage } from '@/api/client'
import type { ParityReport } from '@/inference/parity'
import type { Backend } from '@/inference/runtime'

/**
 * The in-browser runtime: which backend it uses, whether its models are loaded, and the
 * latest parity check against the Python pipeline. The heavy modules load on first use.
 */
export const useBrowserStore = defineStore('browser', () => {
  const backend = ref<Backend | null>(null)
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const checking = ref(false)
  const parity = shallowRef<ParityReport | null>(null)
  const parityError = ref<string | null>(null)
  let preparing: Promise<void> | null = null

  async function chooseBackend(): Promise<Backend> {
    if (backend.value) return backend.value
    const { webgpuAvailable } = await import('@/inference/runtime')
    backend.value = (await webgpuAvailable()) ? 'webgpu' : 'wasm'
    return backend.value
  }

  /** Load the models and run the parity check once per session. */
  function prepare(): Promise<void> {
    if (preparing) return preparing
    preparing = (async () => {
      loading.value = true
      loadError.value = null
      try {
        const chosen = await chooseBackend()
        const { loadModels } = await import('@/inference/runtime')
        await loadModels(chosen)
      } catch (cause) {
        loadError.value = `The models could not be loaded in this browser: ${errorMessage(cause)}`
        preparing = null
        return
      } finally {
        loading.value = false
      }
      await check()
    })()
    return preparing
  }

  async function check(): Promise<ParityReport | null> {
    checking.value = true
    parityError.value = null
    try {
      const chosen = await chooseBackend()
      const { runParity } = await import('@/inference/parity')
      parity.value = await runParity(chosen)
    } catch (cause) {
      parityError.value = errorMessage(cause)
    } finally {
      checking.value = false
    }
    return parity.value
  }

  function useBackend(next: Backend) {
    backend.value = next
    parity.value = null
    preparing = null
  }

  return { backend, loading, loadError, checking, parity, parityError, prepare, check, useBackend }
})
