<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { percent, probability } from '@/lib/format'
import { springTo } from '@/motion/springs'

/**
 * Calibrated confidence as a single-hue ramp bar with its number. The review threshold is a
 * tick on the track; a read under it says so in words next to the number, never by turning
 * the bar a different colour. The fill springs to a new value from wherever it is.
 */
const props = withDefaults(
  defineProps<{
    value: number | null
    label?: string
    threshold?: number | null
    calibrated?: boolean
  }>(),
  { label: 'Calibrated confidence', threshold: null, calibrated: true },
)

const fill = ref<HTMLElement | null>(null)
const scale = computed(() => Math.max(0, Math.min(1, props.value ?? 0)))
const below = computed(
  () => props.value !== null && props.threshold !== null && props.value < props.threshold,
)

function place(animate: boolean) {
  if (!fill.value) return
  if (animate) springTo(fill.value, { scaleX: scale.value })
  else fill.value.style.transform = `scaleX(${scale.value})`
}

onMounted(() => place(false))
watch(scale, () => place(true))
</script>

<template>
  <div class="confidence" data-testid="confidence">
    <div class="head">
      <span class="label">{{ label }}</span>
      <span class="number">
        <strong class="value">{{ probability(value, 1) }}</strong>
        <span v-if="below" class="below">under the review threshold</span>
      </span>
    </div>
    <div class="track" aria-hidden="true">
      <div ref="fill" class="fill" />
      <div
        v-if="threshold !== null"
        class="tick"
        :style="{ left: `${threshold * 100}%` }"
        :title="`Review threshold ${percent(threshold, 0)}`"
      />
    </div>
    <p class="note dx-footnote">
      <template v-if="calibrated"
        >Temperature-scaled on synthetic plates; synthetic results are not real-world
        accuracy.</template
      >
      <template v-else>Not calibrated: a relative score, not a probability.</template>
      <template v-if="threshold !== null">
        Reads under {{ percent(threshold, 0) }} go to review.</template
      >
    </p>
  </div>
</template>

<style scoped>
.confidence {
  display: grid;
  gap: var(--dx-space-2);
}

.head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--dx-space-1) var(--dx-space-3);
}

.label {
  font-size: var(--dx-text-dense);
  font-weight: var(--dx-weight-label);
}

.number {
  display: inline-flex;
  align-items: baseline;
  gap: var(--dx-space-2);
}

.value {
  font-family: var(--dx-font-display);
  font-size: var(--dx-text-title);
  font-weight: var(--dx-weight-title);
  letter-spacing: var(--dx-track-title);
}

.below {
  color: var(--dx-warning);
  font-size: var(--dx-text-footnote);
  font-weight: var(--dx-weight-label);
}

.track {
  position: relative;
  height: 0.5rem;
  border-radius: 999px;
  background: var(--dx-ramp-low);
}

/* one hue, from the surface to the accent: the ramp itself is the fill */
.fill {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(
    to right,
    color-mix(in srgb, var(--dx-ramp-high) 25%, var(--dx-ramp-low)),
    var(--dx-ramp-high)
  );
  transform: scaleX(0);
  transform-origin: left center;
}

.tick {
  position: absolute;
  top: -0.25rem;
  bottom: -0.25rem;
  width: 2px;
  margin-left: -1px;
  border-radius: 1px;
  background: var(--dx-text);
}

.note {
  color: var(--dx-text-2);
}
</style>
