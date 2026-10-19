<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { RouterView } from 'vue-router'

import AppBar from '@/components/AppBar.vue'
import AppFooter from '@/components/AppFooter.vue'
import TabBar from '@/components/TabBar.vue'
import { useServiceStore } from '@/stores/service'
import { useThemeStore } from '@/stores/theme'

useThemeStore()
const service = useServiceStore()
let timer: number | undefined

function refresh() {
  void service.refreshHealth()
  void service.refreshReview()
}

onMounted(() => {
  refresh()
  timer = window.setInterval(refresh, 15000)
})

onBeforeUnmount(() => window.clearInterval(timer))
</script>

<template>
  <a class="skip" href="#main">Skip to content</a>
  <AppBar />
  <main id="main" tabindex="-1">
    <RouterView />
  </main>
  <AppFooter />
  <TabBar />
</template>

<style scoped>
.skip {
  position: absolute;
  top: -48px;
  left: var(--dx-space-2);
  z-index: 40;
  padding: var(--dx-space-2) var(--dx-space-3);
  border-radius: var(--dx-radius-control);
  background: var(--dx-accent-fill);
  color: var(--dx-on-accent);
  font-weight: var(--dx-weight-label);
}

.skip:focus {
  top: var(--dx-space-2);
}

main {
  min-height: calc(100vh - 12rem);
  outline: none;
}
</style>
