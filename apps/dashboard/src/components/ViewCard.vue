<script setup lang="ts">
import { computed } from 'vue'

import { cropUrl } from '@/api/client'
import type { ViewOut } from '@/api/types'
import { fixed, percent, probability } from '@/lib/format'

import StatusLine from './ui/StatusLine.vue'

/** One view: its crop, the detector's confidence, its fusion weight and its hypotheses. */
const props = withDefaults(
  defineProps<{
    view: ViewOut
    /** The view's number as shown (its photo's position in the tray). */
    number?: number | null
    readId?: string | null
    cropSrc?: string | null
    limit?: number
  }>(),
  { number: null, readId: null, cropSrc: null, limit: 5 },
)

const shown = computed(() => props.number ?? props.view.index + 1)
const readable = computed(() => props.view.prediction !== null)
const inSet = computed(() => new Set(props.view.prediction_set ?? []))
const hypotheses = computed(() => props.view.hypotheses.slice(0, props.limit))
// The service keeps the crop of every detection, read or not; so does the browser runtime.
const crop = computed(() => {
  if (props.cropSrc) return props.cropSrc
  return props.readId && props.view.box ? cropUrl(props.readId, props.view.index) : null
})
</script>

<template>
  <article class="view" data-testid="view-card" :aria-labelledby="`view-${view.index}-title`">
    <header class="head">
      <h4 :id="`view-${view.index}-title`">View {{ shown }}</h4>
      <StatusLine v-if="readable" tone="ok" label="Read" />
      <StatusLine v-else tone="bad" label="No plate found" />
    </header>
    <img v-if="crop" class="crop" :src="crop" :alt="`Plate crop read in view ${shown}`" />
    <dl class="dx-facts">
      <dt>Detector</dt>
      <dd>{{ view.box ? `${percent(view.detector_confidence, 1)} confident` : 'no box' }}</dd>
      <dt>Fusion weight</dt>
      <dd>{{ fixed(view.weight, 2) }}</dd>
      <dt>Best reading</dt>
      <dd>
        <span class="dx-plate">{{ view.prediction ?? '–' }}</span>
        <span v-if="view.confidence !== null" class="dx-secondary">
          {{ ' ' + probability(view.confidence, 1) }}</span
        >
      </dd>
    </dl>
    <p class="hyp-title dx-caption">Hypotheses, constrained beam</p>
    <ol v-if="hypotheses.length" class="hyps">
      <li v-for="h in hypotheses" :key="h.tokens" :class="{ inset: inSet.has(h.plate) }">
        <span class="dx-plate plate">{{ h.plate }}</span>
        <span class="bar" aria-hidden="true">
          <span class="fill" :style="{ transform: `scaleX(${h.probability})` }" />
        </span>
        <span class="prob">{{ probability(h.probability, 1) }}</span>
        <span v-if="inSet.has(h.plate)" class="dx-sr-only">(in this view's set)</span>
      </li>
    </ol>
    <p v-else class="dx-secondary dx-footnote">This view proposed no plate.</p>
  </article>
</template>

<style scoped>
.view {
  display: grid;
  align-content: start;
  gap: var(--dx-space-3);
  min-width: 0;
  padding: var(--dx-space-4);
  border: var(--dx-line) solid var(--dx-border);
  border-radius: var(--dx-radius-panel);
  background: var(--dx-surface);
}

.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--dx-space-2);
}

.crop {
  display: block;
  width: 100%;
  max-height: 4.5rem;
  object-fit: contain;
  border-radius: var(--dx-radius-control);
  background: var(--dx-surface-inset);
}

.hyp-title {
  color: var(--dx-text-2);
}

.hyps {
  display: grid;
  gap: var(--dx-space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.hyps li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 4rem 3.75rem;
  align-items: center;
  gap: var(--dx-space-2);
  padding: 2px var(--dx-space-2);
  border-radius: var(--dx-radius-control);
  font-size: var(--dx-text-dense);
}

.hyps li.inset {
  background: var(--dx-accent-soft);
}

.plate {
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar {
  height: 0.375rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--dx-ramp-low);
}

.fill {
  display: block;
  height: 100%;
  background: var(--dx-chart-mark);
  transform-origin: left center;
}

.prob {
  text-align: right;
}
</style>
