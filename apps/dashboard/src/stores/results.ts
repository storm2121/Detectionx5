import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, errorMessage } from '@/api/client'
import type { ResultEntry } from '@/api/types'

/** The committed results files, fetched once each and shared by the pages. */
export const useResultsStore = defineStore('results', () => {
  const index = ref<ResultEntry[] | null>(null)
  const files = ref<Record<string, unknown>>({})
  const errors = ref<Record<string, string>>({})
  const pending = new Map<string, Promise<unknown>>()

  async function loadIndex(): Promise<ResultEntry[]> {
    if (index.value) return index.value
    try {
      index.value = await api.results()
      delete errors.value.index
    } catch (cause) {
      errors.value.index = errorMessage(cause)
      index.value = null
      return []
    }
    return index.value
  }

  async function load<T>(name: string): Promise<T | null> {
    if (name in files.value) return files.value[name] as T
    let request = pending.get(name)
    if (!request) {
      request = api.result<T>(name)
      pending.set(name, request)
    }
    try {
      const payload = (await request) as T
      files.value[name] = payload
      delete errors.value[name]
      return payload
    } catch (cause) {
      errors.value[name] = errorMessage(cause)
      return null
    } finally {
      pending.delete(name)
    }
  }

  function has(name: string): boolean {
    return index.value?.some((entry) => entry.name === name) ?? false
  }

  return { index, files, errors, loadIndex, load, has }
})
