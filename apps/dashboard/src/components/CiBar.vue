<script setup lang="ts">
import { scaleLinear } from 'd3'
import { computed } from 'vue'

import type { Estimate } from '@/api/results'

/**
 * An estimate's interval as a small bar beside its number: the interval in a light step of
 * the accent and the point estimate as a tick. Both move by transform alone when the
 * estimate changes, on the spring curve.
 */
const props = withDefaults(
  defineProps<{ estimate: Estimate; domain?: [number, number]; width?: number }>(),
  { domain: () => [0, 1], width: 88 },
)

const x = computed(() => scaleLinear().domain(props.domain).range([0, props.width]).clamp(true))
const low = computed(() => x.value(props.estimate.ci_low))
const span = computed(() =>
  Math.max(0.02, (x.value(props.estimate.ci_high) - low.value) / props.width),
)
const value = computed(() => x.value(props.estimate.value))
</script>

<template>
  <span class="ci" :style="{ width: `${width}px` }" aria-hidden="true" data-testid="ci-bar">
    <span class="track" />
    <span class="interval" :style="{ transform: `translateX(${low}px) scaleX(${span})` }" />
    <span class="value" :style="{ transform: `translateX(${value - 1}px)` }" />
  </span>
</template>

<style scoped>
.ci {
  position: relative;
  display: inline-block;
  height: 0.75rem;
  vertical-align: middle;
}

.track {
  position: absolute;
  top: 50%;
  right: 0;
  left: 0;
  height: 1px;
  background: var(--dx-chart-axis);
}

.interval {
  position: absolute;
  top: 2px;
  bottom: 2px;
  left: 0;
  width: 100%;
  border-radius: 2px;
  background: color-mix(in srgb, var(--dx-chart-mark) 30%, transparent);
  transform-origin: left center;
  transition: transform 450ms cubic-bezier(0.25, 0.1, 0.1, 1);
}

.value {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 2px;
  border-radius: 1px;
  background: var(--dx-chart-mark);
  transition: transform 450ms cubic-bezier(0.25, 0.1, 0.1, 1);
}

@media (prefers-reduced-motion: reduce) {
  .interval,
  .value {
    transition: none;
  }
}
</style>
