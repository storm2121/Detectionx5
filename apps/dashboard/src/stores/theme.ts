import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import { DARK_CLASS } from '@/theme/preset'

export type ThemeChoice = 'system' | 'light' | 'dark'
const KEY = 'dx-theme'

function readChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  } catch {
    // storage blocked: follow the system
  }
  return 'system'
}

function writeChoice(choice: ThemeChoice): void {
  try {
    window.localStorage.setItem(KEY, choice)
  } catch {
    // storage blocked: the choice lasts for this page only
  }
}

export function applyTheme(theme: 'light' | 'dark', root: HTMLElement = document.documentElement) {
  root.classList.toggle(DARK_CLASS, theme === 'dark')
  root.dataset.theme = theme
}

/** Light or dark: the system's preference until the viewer picks one. */
export const useThemeStore = defineStore('theme', () => {
  const choice = ref<ThemeChoice>(readChoice())
  const media =
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-color-scheme: dark)')
      : null
  const systemDark = ref(media?.matches ?? false)
  media?.addEventListener?.('change', (event) => {
    systemDark.value = event.matches
  })
  const resolved = computed<'light' | 'dark'>(() =>
    choice.value === 'system' ? (systemDark.value ? 'dark' : 'light') : choice.value,
  )
  // Synchronously, so that components reading colour tokens in the same tick (the D3
  // scales) already see the new scheme.
  watch(resolved, (theme) => applyTheme(theme), { immediate: true, flush: 'sync' })

  function set(next: ThemeChoice) {
    choice.value = next
    writeChoice(next)
  }

  function toggle() {
    set(resolved.value === 'dark' ? 'light' : 'dark')
  }

  return { choice, resolved, set, toggle }
})
