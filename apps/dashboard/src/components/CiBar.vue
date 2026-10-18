<script setup lang="ts">
import { scaleLinear } from 'd3'
import { computed } from 'vue'

import type { Estimate } from '@/api/results'

const props = withDefaults(
  defineProps<{ estimate: Estimate; domain?: [number, number]; width?: number }>(),
  { domain: () => [0, 1], width: 96 },
)

const x = computed(() =>
  scaleLinear()
    .domain(props.domain)
    .range([2, props.width - 2])
    .clamp(true),
)
const low = computed(() => x.value(props.estimate.ci_low))
const high = computed(() => x.value(props.estimate.ci_high))
const value = computed(() => x.value(props.estimate.value))
</script>

<template>
  <svg
    class="ci"
    :width="width"
    height="12"
    :viewBox="`0 0 ${width} 12`"
    aria-hidden="true"
    data-testid="ci-bar"
  >
    <line class="track" :x1="2" :x2="width - 2" y1="6" y2="6" />
    <rect class="interval" :x="low" y="2" :width="Math.max(2, high - low)" height="8" rx="2" />
    <line class="value" :x1="value" :x2="value" y1="0" y2="12" />
  </svg>
</template>

<style scoped>
.ci {
  display: block;
  overflow: visible;
}

.track {
  stroke: var(--dx-border-strong);
  stroke-width: 1;
}

.interval {
  fill: color-mix(in srgb, var(--dx-chart-ink) 30%, transparent);
}

.value {
  stroke: var(--dx-chart-ink);
  stroke-width: 2;
}
</style>
