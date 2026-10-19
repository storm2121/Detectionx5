import './styles/fonts.css'
import './styles/tokens.css'
import './styles/base.css'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { makeRouter } from './router'

const app = createApp(App)
app.use(createPinia())
app.use(makeRouter())
app.mount('#app')
