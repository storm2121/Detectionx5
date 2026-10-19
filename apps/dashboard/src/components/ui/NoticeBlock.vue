<script setup lang="ts">
import { CircleAlert, Info, TriangleAlert } from '@lucide/vue'
import { computed } from 'vue'

import DxIcon from './DxIcon.vue'

/**
 * A notice inside the flow of a page. `note` explains (the synthetic label), `warning`
 * warns before a problem, `error` says what happened and what to do; each has its own
 * colour, icon and role, so none relies on colour alone.
 */
const props = withDefaults(
  defineProps<{ tone?: 'note' | 'warning' | 'error'; title?: string; message?: string }>(),
  { tone: 'note', title: '', message: '' },
)
const icon = computed(() =>
  props.tone === 'error' ? CircleAlert : props.tone === 'warning' ? TriangleAlert : Info,
)
const role = computed(() => (props.tone === 'error' ? 'alert' : 'note'))
</script>

<template>
  <div
    class="notice"
    :class="tone"
    :role="role"
    :data-testid="tone === 'error' ? 'error-note' : undefined"
  >
    <DxIcon :icon="icon" :size="16" class="icon" />
    <div class="body">
      <strong v-if="title" class="title">{{ title }}</strong>
      <span v-if="message">{{ message }}</span>
      <slot />
    </div>
  </div>
</template>

<style scoped>
.notice {
  display: flex;
  align-items: flex-start;
  gap: var(--dx-space-2);
  padding: var(--dx-space-3) var(--dx-space-4);
  border: var(--dx-line) solid var(--dx-border);
  border-radius: var(--dx-radius-panel);
  background: var(--dx-surface);
  color: var(--dx-text);
  font-size: var(--dx-text-dense);
  line-height: var(--dx-leading-dense);
}

.icon {
  margin-top: 0.125rem;
  color: var(--dx-text-2);
}

.body {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.title {
  font-weight: var(--dx-weight-title);
}

.warning {
  border-color: color-mix(in srgb, var(--dx-warning) 40%, var(--dx-border));
  background: var(--dx-warning-soft);
}

.warning .icon,
.warning .title {
  color: var(--dx-warning);
}

.error {
  border-color: color-mix(in srgb, var(--dx-danger) 40%, var(--dx-border));
  background: var(--dx-danger-soft);
}

.error .icon,
.error .title {
  color: var(--dx-danger);
}
</style>
