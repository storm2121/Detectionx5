import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, errorMessage } from '@/api/client'
import type { Health, ModelsOut, ReviewSummary } from '@/api/types'

/**
 * Service health and the review counts (polled by the shell, so every page's navigation
 * says how many reads wait), and the active models (loaded once).
 */
export const useServiceStore = defineStore('service', () => {
  const health = ref<Health | null>(null)
  const healthError = ref<string | null>(null)
  const review = ref<ReviewSummary | null>(null)
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

  async function refreshReview() {
    try {
      review.value = await api.reviewSummary()
    } catch {
      review.value = null
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

  return {
    health,
    healthError,
    review,
    models,
    modelsError,
    refreshHealth,
    refreshReview,
    loadModels,
  }
})
