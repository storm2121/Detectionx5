<script setup lang="ts">
import { CircleAlert, CircleCheck, CircleDashed, Moon, Sun, TriangleAlert } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import DxIcon from '@/components/ui/DxIcon.vue'
import IconButton from '@/components/ui/IconButton.vue'
import { navItems } from '@/lib/nav'
import { useServiceStore } from '@/stores/service'
import { useThemeStore } from '@/stores/theme'

/**
 * The top bar: a translucent material that content scrolls under, with a soft fade where it
 * meets the content once the page has scrolled (no divider line). It names the page: the
 * current page is the marked item in the navigation, and at phone width, where the pages
 * move to the tab bar, the bar shows the page's name.
 */
const theme = useThemeStore()
const service = useServiceStore()
const route = useRoute()

const items = computed(() => navItems(service.review))
const title = computed(() =>
  typeof route.meta.title === 'string' ? route.meta.title : 'DetectionX5',
)
const next = computed(() => (theme.resolved === 'dark' ? 'light' : 'dark'))
const health = computed(() => {
  if (service.health) {
    return service.health.status === 'ok'
      ? { tone: 'ok', text: 'Service ready', icon: CircleCheck }
      : { tone: 'warn', text: 'Service degraded', icon: TriangleAlert }
  }
  if (service.healthError) return { tone: 'bad', text: 'Service unreachable', icon: CircleAlert }
  return { tone: 'neutral', text: 'Checking service', icon: CircleDashed }
})

const scrolled = ref(false)
function onScroll() {
  scrolled.value = window.scrollY > 2
}
onMounted(() => {
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))

function isCurrent(to: string) {
  return route.path === to || (to === '/read' && route.path.startsWith('/reads/'))
}
</script>

<template>
  <header class="bar" :class="{ scrolled }">
    <div class="inner">
      <RouterLink to="/read" class="brand">DetectionX5</RouterLink>
      <span class="page-name" aria-hidden="true">{{ title }}</span>
      <nav class="nav" aria-label="Pages">
        <ul>
          <li v-for="item in items" :key="item.to">
            <RouterLink
              :to="item.to"
              class="link"
              :class="{ current: isCurrent(item.to) }"
              :aria-current="isCurrent(item.to) ? 'page' : undefined"
            >
              {{ item.label }}
            </RouterLink>
          </li>
        </ul>
      </nav>
      <div class="tools">
        <span class="health" :class="health.tone" role="status" data-testid="service-health">
          <DxIcon :icon="health.icon" :size="16" />
          <span class="health-text">{{ health.text }}</span>
        </span>
        <IconButton
          :icon="theme.resolved === 'dark' ? Sun : Moon"
          :label="`Switch to the ${next} theme`"
          data-testid="theme-toggle"
          @click="theme.toggle()"
        />
      </div>
    </div>
  </header>
</template>

<style scoped>
.bar {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--dx-material);
  -webkit-backdrop-filter: var(--dx-material-filter);
  backdrop-filter: var(--dx-material-filter);
  box-shadow: inset 0 1px 0 var(--dx-material-edge);
}

/* the scroll-edge fade: content dissolves into the bar instead of meeting a line */
.bar::after {
  position: absolute;
  top: 100%;
  right: 0;
  left: 0;
  height: var(--dx-space-3);
  content: '';
  background: linear-gradient(to bottom, var(--dx-scrim-edge), transparent);
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--dx-fade-ms) linear;
}

.bar.scrolled::after {
  opacity: 1;
}

.inner {
  display: flex;
  align-items: center;
  gap: var(--dx-space-5);
  max-width: var(--dx-content-width);
  min-height: var(--dx-bar-height);
  margin: 0 auto;
  padding: 0 var(--dx-gutter);
}

.brand {
  flex: none;
  color: var(--dx-text);
  font-weight: var(--dx-weight-title);
  letter-spacing: var(--dx-track-title);
  text-decoration: none;
}

.page-name {
  display: none;
}

.nav {
  flex: 1 1 auto;
  min-width: 0;
}

.nav ul {
  display: flex;
  gap: var(--dx-space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.link {
  display: block;
  padding: var(--dx-space-1) var(--dx-space-3);
  border-radius: var(--dx-radius-control);
  color: var(--dx-text-2);
  font-size: var(--dx-text-dense);
  font-weight: var(--dx-weight-label);
  line-height: 1.75rem;
  text-decoration: none;
  white-space: nowrap;
}

.link:hover {
  color: var(--dx-text);
  background: color-mix(in srgb, var(--dx-text) 6%, transparent);
}

.link.current {
  color: var(--dx-text);
  background: color-mix(in srgb, var(--dx-text) 9%, transparent);
}

.tools {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--dx-space-2);
}

.health {
  display: inline-flex;
  align-items: center;
  gap: var(--dx-space-1);
  color: var(--dx-text-2);
  font-family: var(--dx-font-small);
  font-size: var(--dx-text-caption);
  letter-spacing: var(--dx-track-caption);
  white-space: nowrap;
}

.health.ok :deep(.dx-icon) {
  color: var(--dx-success);
}

.health.warn :deep(.dx-icon) {
  color: var(--dx-warning);
}

.health.bad :deep(.dx-icon) {
  color: var(--dx-danger);
}

@media (max-width: 1080px) {
  .brand {
    display: none;
  }
}

@media (max-width: 720px) {
  .nav,
  .brand {
    display: none;
  }

  .page-name {
    display: block;
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    font-size: var(--dx-text-headline);
    font-weight: var(--dx-weight-title);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .health-text {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
  }
}
</style>
