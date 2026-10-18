import '../src/theme/fonts.css'
import '../src/theme/tokens.css'
import '../src/theme/base.css'

import { setup, type Preview } from '@storybook/vue3'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'

import { useThemeStore } from '../src/stores/theme'
import { ConsolePreset, DARK_CLASS } from '../src/theme/preset'

const pinia = createPinia()
setActivePinia(pinia)

setup((app) => {
  app.use(pinia)
  app.use(PrimeVue, {
    theme: {
      preset: ConsolePreset,
      options: { darkModeSelector: `.${DARK_CLASS}`, cssLayer: false },
    },
  })
})

const preview: Preview = {
  globalTypes: {
    theme: {
      description: 'Colour theme',
      toolbar: { title: 'Theme', icon: 'mirror', items: ['light', 'dark'], dynamicTitle: true },
    },
  },
  initialGlobals: { theme: 'light' },
  decorators: [
    (story, context) => {
      useThemeStore(pinia).set(context.globals.theme === 'dark' ? 'dark' : 'light')
      return {
        components: { story },
        template:
          '<div style="padding: 16px; background: var(--dx-bg); color: var(--dx-text); min-height: 100%"><story /></div>',
      }
    },
  ],
  parameters: {
    layout: 'fullscreen',
    controls: { expanded: true },
    a11y: { element: '#storybook-root' },
  },
}

export default preview
