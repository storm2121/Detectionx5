<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { springTo } from '@/motion/springs'

/**
 * A progress bar that fills with the job's real progress: each update springs from where
 * the bar is to the new value (no jump, no fake easing towards a guess).
 */
const props = withDefaults(
  defineProps<{ value: number; label: string; size?: 'regular' | 'small' }>(),
  {
    size: 'regular',
  },
)
const fill = ref<HTMLElement | null>(null)

function place(animate: boolean) {
  if (!fill.value) return
  const scale = Math.max(0, Math.min(1, props.value))
  if (animate) springTo(fill.value, { scaleX: scale })
  else fill.value.style.transform = `scaleX(${scale})`
}

onMounted(() => place(false))
watch(
  () => props.value,
  () => place(true),
)
</script>

<template>
  <div
    class="progress"
    :class="size"
    role="progressbar"
    :aria-label="label"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-valuenow="Math.round(value * 100)"
  >
    <div ref="fill" class="fill" />
  </div>
</template>

<style scoped>
.progress {
  position: relative;
  height: 0.5rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--dx-ramp-low);
}

.progress.small {
  width: 6rem;
  height: 0.375rem;
}

.fill {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: var(--dx-accent-fill);
  transform: scaleX(0);
  transform-origin: left center;
}
</style>
