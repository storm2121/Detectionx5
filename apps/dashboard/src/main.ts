import './theme/fonts.css'
import './theme/tokens.css'
import './theme/base.css'

import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { createApp } from 'vue'

import App from './App.vue'
import { makeRouter } from './router'
import { ConsolePreset, DARK_CLASS } from './theme/preset'

const app = createApp(App)
app.use(createPinia())
app.use(makeRouter())
app.use(PrimeVue, {
  theme: {
    preset: ConsolePreset,
    options: { darkModeSelector: `.${DARK_CLASS}`, cssLayer: false },
  },
})
app.mount('#app')
