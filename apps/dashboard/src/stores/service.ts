import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, errorMessage } from '@/api/client'
import type { Health, ModelsOut } from '@/api/types'

/** Service health (polled by the header) and the active models (loaded once). */
export const useServiceStore = defineStore('service', () => {
  const health = ref<Health | null>(null)
  const healthError = ref<string | null>(null)
  const models = ref<ModelsOut | null>(null)
  const modelsError = ref<string | null>(null)
  let modelsRequest: Promise<void> | null = null

  async function refreshHealth() {
    try {
      health.value = await api.health()
      healthError.value = null
    } catch (cause) {
      health.value = null
      healthError.value = errorMessage(cause)
    }
  }

  function loadModels(force = false): Promise<void> {
    if (modelsRequest && !force) return modelsRequest
    modelsRequest = (async () => {
      try {
        models.value = await api.models()
        modelsError.value = null
      } catch (cause) {
        modelsError.value = errorMessage(cause)
        modelsRequest = null
      }
    })()
    return modelsRequest
  }

  return { health, healthError, models, modelsError, refreshHealth, loadModels }
})
