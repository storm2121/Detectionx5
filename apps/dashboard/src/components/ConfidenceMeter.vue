<script setup lang="ts">
import { computed } from 'vue'

import { percent, probability } from '@/lib/format'

const props = withDefaults(
  defineProps<{
    value: number | null
    label?: string
    /** The service's review threshold; the bar turns amber below it. */
    threshold?: number | null
    calibrated?: boolean
  }>(),
  { label: 'Confidence', threshold: null, calibrated: true },
)

const scale = computed(() => `scaleX(${Math.max(0, Math.min(1, props.value ?? 0))})`)
const low = computed(
  () => props.value !== null && props.threshold !== null && props.value < props.threshold,
)
</script>

<template>
  <div class="meter" data-testid="confidence">
    <div class="head">
      <span class="label">{{ label }}</span>
      <strong class="dx-num value">{{ probability(value, 1) }}</strong>
    </div>
    <div class="track" aria-hidden="true">
      <div class="fill" :class="{ low }" :style="{ transform: scale }" />
      <div
        v-if="threshold !== null"
        class="mark"
        :style="{ left: `${threshold * 100}%` }"
        :title="`Review threshold ${percent(threshold, 0)}`"
      />
    </div>
    <p class="note">
      <template v-if="calibrated"
        >Calibrated posterior (temperature-scaled on synthetic data)</template
      >
      <template v-else>Not calibrated: a relative score, not a probability</template>
      <template v-if="threshold !== null">; review below {{ percent(threshold, 0) }}</template>
    </p>
  </div>
</template>

<style scoped>
.meter {
  display: grid;
  gap: 6px;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--dx-space-2);
}

.label {
  color: var(--dx-text-muted);
  font-size: var(--dx-text-sm);
}

.value {
  font-size: var(--dx-text-xl);
}

.track {
  position: relative;
  height: 8px;
  border-radius: 999px;
  background: var(--dx-surface-sunken);
  border: 1px solid var(--dx-border);
}

.fill {
  height: 100%;
  border-radius: inherit;
  background: var(--dx-accent);
  transform-origin: left center;
  transition: transform 240ms ease;
}

.fill.low {
  background: var(--dx-chart-gap);
}

.mark {
  position: absolute;
  top: -4px;
  bottom: -4px;
  width: 2px;
  margin-left: -1px;
  background: var(--dx-text);
  border-radius: 1px;
}

.note {
  color: var(--dx-text-muted);
  font-size: var(--dx-text-xs);
}
</style>
