<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { useServiceStore } from '@/stores/service'
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()
const service = useServiceStore()

const items = [
  { to: '/read', label: 'Read' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/review', label: 'Review' },
  { to: '/evaluation', label: 'Evaluation' },
  { to: '/models', label: 'Models' },
  { to: '/methods', label: 'Methods' },
]

const next = computed(() => (theme.resolved === 'dark' ? 'light' : 'dark'))
const health = computed(() => {
  if (service.health) {
    const ok = service.health.status === 'ok'
    return { tone: ok ? 'ok' : 'warn', text: ok ? 'Service ready' : 'Service degraded' }
  }
  if (service.healthError) return { tone: 'bad', text: 'Service unreachable' }
  return { tone: 'neutral', text: 'Checking service' }
})
</script>

<template>
  <header class="bar">
    <div class="inner">
      <RouterLink to="/read" class="brand">
        <svg class="logo" viewBox="0 0 32 32" aria-hidden="true">
          <rect x="2" y="8" width="28" height="16" rx="3" fill="currentColor" />
          <rect x="5" y="11" width="22" height="10" rx="1.5" fill="var(--dx-surface)" />
          <path
            d="M8 16h5M16 13v6M19 16h5"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          />
        </svg>
        <span class="name">DetectionX5</span>
        <span class="sub">console</span>
      </RouterLink>
      <nav class="nav" aria-label="Main">
        <ul>
          <li v-for="item in items" :key="item.to">
            <RouterLink :to="item.to" active-class="active">{{ item.label }}</RouterLink>
          </li>
        </ul>
      </nav>
      <div class="tools">
        <span class="health" :class="health.tone" role="status" data-testid="service-health">
          <span class="dot" aria-hidden="true" />{{ health.text }}
        </span>
        <button
          type="button"
          class="theme"
          :aria-label="`Switch to the ${next} theme`"
          :title="`Switch to the ${next} theme`"
          data-testid="theme-toggle"
          @click="theme.toggle()"
        >
          <svg v-if="theme.resolved === 'dark'" viewBox="0 0 20 20" aria-hidden="true">
            <circle cx="10" cy="10" r="3.6" fill="currentColor" />
            <path
              d="M10 1.8v2.4M10 15.8v2.4M1.8 10h2.4M15.8 10h2.4M4.2 4.2l1.7 1.7M14.1 14.1l1.7 1.7M4.2 15.8l1.7-1.7M14.1 5.9l1.7-1.7"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
            />
          </svg>
          <svg v-else viewBox="0 0 20 20" aria-hidden="true">
            <path d="M16.5 12.6A7 7 0 0 1 7.4 3.5a7 7 0 1 0 9.1 9.1Z" fill="currentColor" />
          </svg>
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.bar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: color-mix(in srgb, var(--dx-surface) 92%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--dx-border);
}

.inner {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--dx-space-4);
  max-width: var(--dx-content-width);
  margin: 0 auto;
  padding: var(--dx-space-2) var(--dx-gutter);
  min-height: 56px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--dx-space-2);
  color: var(--dx-text);
  text-decoration: none;
  white-space: nowrap;
}

.logo {
  width: 28px;
  height: 28px;
  color: var(--dx-accent);
}

.name {
  font-weight: 700;
  letter-spacing: -0.01em;
}

.sub {
  color: var(--dx-text-muted);
  font-size: var(--dx-text-sm);
}

.nav {
  min-width: 0;
}

.nav ul {
  display: flex;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
  overflow-x: auto;
  scrollbar-width: none;
}

.nav a {
  display: block;
  padding: 6px 12px;
  border-radius: var(--dx-radius-s);
  color: var(--dx-text-muted);
  font-weight: 550;
  text-decoration: none;
  white-space: nowrap;
}

.nav a:hover {
  color: var(--dx-text);
  background: var(--dx-surface-sunken);
}

.nav a.active {
  color: var(--dx-accent-strong);
  background: var(--dx-accent-soft);
}

.tools {
  display: flex;
  align-items: center;
  gap: var(--dx-space-2);
}

.health {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--dx-text-xs);
  color: var(--dx-text-muted);
  white-space: nowrap;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dx-border-strong);
}

.health.ok .dot {
  background: #22c55e;
}

.health.warn .dot {
  background: #f59e0b;
}

.health.bad .dot {
  background: #ef4444;
}

.theme {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--dx-border);
  border-radius: var(--dx-radius-s);
  background: var(--dx-surface);
  color: var(--dx-text);
  cursor: pointer;
}

.theme:hover {
  background: var(--dx-surface-sunken);
}

.theme svg {
  width: 18px;
  height: 18px;
}

@media (max-width: 860px) {
  .inner {
    grid-template-columns: 1fr auto;
    row-gap: var(--dx-space-1);
  }

  .nav {
    grid-column: 1 / -1;
    grid-row: 2;
  }

  .sub {
    display: none;
  }
}

@media (max-width: 420px) {
  .health {
    font-size: 0;
    gap: 0;
  }
}
</style>
