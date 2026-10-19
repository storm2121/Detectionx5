import '../src/styles/fonts.css'
import '../src/styles/tokens.css'
import '../src/styles/base.css'

import { setup, type Preview } from '@storybook/vue3'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import { makeRouter } from '../src/router'

const pinia = createPinia()
setActivePinia(pinia)
const router = makeRouter(createMemoryHistory())

setup((app) => {
  app.use(pinia)
  app.use(router)
})

/**
 * Every story renders in both themes at once, side by side (stacked when the canvas is
 * narrow): the light frame and the dark frame each carry `data-theme`, so the tokens of
 * that theme apply inside it. The toolbar can isolate one theme.
 */
const preview: Preview = {
  globalTypes: {
    theme: {
      description: 'Colour theme',
      toolbar: {
        title: 'Theme',
        icon: 'mirror',
        items: [
          { value: 'both', title: 'Light and dark' },
          { value: 'light', title: 'Light' },
          { value: 'dark', title: 'Dark' },
        ],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: { theme: 'both' },
  decorators: [
    (story, context) => {
      const mode = String(context.globals.theme ?? 'both')
      return {
        components: { story },
        setup: () => ({ mode }),
        template: `<div class="sb-frames" :data-mode="mode">
          <div v-if="mode !== 'dark'" class="sb-frame" data-theme="light"><story /></div>
          <div v-if="mode !== 'light'" class="sb-frame" data-theme="dark"><story /></div>
        </div>`,
      }
    },
  ],
  parameters: {
    layout: 'fullscreen',
    controls: { expanded: true },
    backgrounds: { disable: true },
    a11y: { element: '#storybook-root' },
  },
}

export default preview
