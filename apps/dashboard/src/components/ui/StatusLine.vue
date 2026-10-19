<script setup lang="ts">
import { Check, CircleAlert, Circle, Clock, TriangleAlert } from '@lucide/vue'
import { computed } from 'vue'

import type { Tone } from '@/lib/plate'

import DxIcon from './DxIcon.vue'

/**
 * A state in words: an icon and a sentence-case label in the state's colour. Success,
 * warning and danger read differently in colour, icon and wording; a neutral state is grey.
 */
const props = withDefaults(defineProps<{ tone?: Tone; label: string }>(), { tone: 'neutral' })
const icon = computed(() => {
  switch (props.tone) {
    case 'ok':
      return Check
    case 'warn':
      return TriangleAlert
    case 'bad':
      return CircleAlert
    case 'info':
      return Clock
    default:
      return Circle
  }
})
</script>

<template>
  <span class="status" :class="tone" data-testid="status-pill">
    <DxIcon :icon="icon" :size="16" />
    <span>{{ label }}</span>
  </span>
</template>

<style scoped>
.status {
  display: inline-flex;
  align-items: center;
  gap: var(--dx-space-1);
  color: var(--dx-text-2);
  font-size: var(--dx-text-dense);
  font-weight: var(--dx-weight-label);
  line-height: 1.25;
  white-space: nowrap;
}

.ok {
  color: var(--dx-success);
}

.warn {
  color: var(--dx-warning);
}

.bad {
  color: var(--dx-danger);
}

.info {
  color: var(--dx-accent);
}
</style>
