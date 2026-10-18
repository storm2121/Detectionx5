<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { RouterView } from 'vue-router'

import AppFooter from '@/components/AppFooter.vue'
import AppHeader from '@/components/AppHeader.vue'
import { useServiceStore } from '@/stores/service'
import { useThemeStore } from '@/stores/theme'

useThemeStore()
const service = useServiceStore()
let timer: number | undefined

onMounted(() => {
  void service.refreshHealth()
  timer = window.setInterval(() => void service.refreshHealth(), 15000)
})

onBeforeUnmount(() => window.clearInterval(timer))
</script>

<template>
  <a class="skip" href="#main">Skip to content</a>
  <AppHeader />
  <main id="main" tabindex="-1">
    <RouterView />
  </main>
  <AppFooter />
</template>

<style scoped>
.skip {
  position: absolute;
  left: var(--dx-space-2);
  top: -48px;
  z-index: 20;
  padding: var(--dx-space-2) var(--dx-space-3);
  border-radius: var(--dx-radius-s);
  background: var(--dx-accent);
  color: var(--dx-on-accent);
  font-weight: 600;
}

.skip:focus {
  top: var(--dx-space-2);
}

main {
  min-height: calc(100vh - 160px);
  outline: none;
}
</style>
