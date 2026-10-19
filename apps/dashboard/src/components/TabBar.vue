<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import DxIcon from '@/components/ui/DxIcon.vue'
import { navItems } from '@/lib/nav'
import { vPress } from '@/motion/press'
import { useServiceStore } from '@/stores/service'

/**
 * The pages at phone width: a translucent tab bar at the bottom, every page one tap away,
 * each tab an icon over its name and at least 44 px tall. It is the only translucent
 * surface at the bottom of the screen, so no two materials ever stack.
 */
const service = useServiceStore()
const route = useRoute()
const items = computed(() => navItems(service.review))
const waiting = computed(() => service.review?.pending ?? 0)

function isCurrent(to: string) {
  return route.path === to || (to === '/read' && route.path.startsWith('/reads/'))
}
</script>

<template>
  <nav class="tabs" aria-label="Pages">
    <RouterLink
      v-for="item in items"
      :key="item.to"
      v-press
      :to="item.to"
      class="tab"
      :class="{ current: isCurrent(item.to) }"
      :aria-current="isCurrent(item.to) ? 'page' : undefined"
      :aria-label="item.label"
    >
      <span class="icon">
        <DxIcon :icon="item.icon" :size="20" />
        <span v-if="item.to === '/review' && waiting > 0" class="badge" aria-hidden="true">
          {{ waiting > 99 ? '99+' : waiting }}
        </span>
      </span>
      <span class="name" aria-hidden="true">{{ item.short }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.tabs {
  display: none;
}

@media (max-width: 720px) {
  .tabs {
    position: fixed;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 20;
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    padding: var(--dx-space-1) var(--dx-space-1)
      calc(var(--dx-space-1) + env(safe-area-inset-bottom));
    background: var(--dx-material);
    -webkit-backdrop-filter: var(--dx-material-filter);
    backdrop-filter: var(--dx-material-filter);
    box-shadow: inset 0 1px 0 var(--dx-material-edge);
  }

  .tab {
    display: grid;
    justify-items: center;
    align-content: center;
    gap: 2px;
    min-height: var(--dx-tab-height);
    border-radius: var(--dx-radius-control);
    color: var(--dx-text-2);
    text-decoration: none;
    -webkit-tap-highlight-color: transparent;
  }

  .tab.current {
    color: var(--dx-accent);
  }

  .icon {
    position: relative;
    display: grid;
    place-items: center;
  }

  .badge {
    position: absolute;
    top: -6px;
    left: 12px;
    min-width: 1.125rem;
    padding: 0 4px;
    border-radius: 999px;
    background: var(--dx-accent-fill);
    color: var(--dx-on-accent);
    font-family: var(--dx-font-small);
    font-size: 0.6875rem;
    font-weight: var(--dx-weight-title);
    line-height: 1.125rem;
    text-align: center;
  }

  .name {
    max-width: 100%;
    overflow: hidden;
    font-family: var(--dx-font-small);
    font-size: 0.6875rem;
    font-weight: var(--dx-weight-label);
    letter-spacing: var(--dx-track-caption);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
