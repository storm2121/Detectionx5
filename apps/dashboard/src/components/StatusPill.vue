<script setup lang="ts">
import type { Tone } from '@/lib/plate'

withDefaults(defineProps<{ tone?: Tone; label: string }>(), { tone: 'neutral' })
</script>

<template>
  <span class="pill" :class="tone" data-testid="status-pill">
    <span class="dot" aria-hidden="true" />{{ label }}
  </span>
</template>

<style scoped>
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: var(--dx-text-xs);
  font-weight: 600;
  line-height: 1.6;
  white-space: nowrap;
  border: 1px solid transparent;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}

.ok {
  background: var(--dx-ok-soft);
  color: var(--dx-ok);
}

.warn {
  background: var(--dx-warn-soft);
  color: var(--dx-warn);
}

.bad {
  background: var(--dx-bad-soft);
  color: var(--dx-bad);
}

.info {
  background: var(--dx-info-soft);
  color: var(--dx-info);
}

.neutral {
  background: var(--dx-surface-sunken);
  color: var(--dx-text-muted);
  border-color: var(--dx-border);
}
</style>
