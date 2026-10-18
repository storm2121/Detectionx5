<script setup lang="ts">
import { computed } from 'vue'

import { cropUrl } from '@/api/client'
import type { ViewOut } from '@/api/types'
import { fixed, percent, probability } from '@/lib/format'

import StatusPill from './StatusPill.vue'

const props = withDefaults(
  defineProps<{ view: ViewOut; readId?: string | null; limit?: number }>(),
  { readId: null, limit: 5 },
)

const number = computed(() => props.view.index + 1)
const readable = computed(() => props.view.prediction !== null)
const inSet = computed(() => new Set(props.view.prediction_set ?? []))
const hypotheses = computed(() => props.view.hypotheses.slice(0, props.limit))
const crop = computed(() =>
  props.readId && readable.value ? cropUrl(props.readId, props.view.index) : null,
)
</script>

<template>
  <article class="view dx-card" data-testid="view-card" :aria-labelledby="`view-${number}-title`">
    <header class="head">
      <h3 :id="`view-${number}-title`">View {{ number }}</h3>
      <StatusPill v-if="readable" tone="ok" label="read" />
      <StatusPill v-else tone="bad" label="no plate found" />
    </header>
    <img v-if="crop" class="crop" :src="crop" :alt="`Plate crop read in view ${number}`" />
    <dl class="dx-dl">
      <dt>Detector</dt>
      <dd class="dx-num">
        {{ view.box ? percent(view.detector_confidence, 1) : 'no box' }}
      </dd>
      <dt>Fusion weight</dt>
      <dd class="dx-num">{{ fixed(view.weight, 2) }}</dd>
      <dt>Best reading</dt>
      <dd>
        <span class="dx-plate-text">{{ view.prediction ?? '–' }}</span>
        <span v-if="view.confidence !== null" class="dx-num dx-muted">
          {{ ' ' + probability(view.confidence, 1) }}</span
        >
      </dd>
    </dl>
    <h4 class="hyp-title">Hypotheses (constrained beam)</h4>
    <ol v-if="hypotheses.length" class="hyps">
      <li v-for="h in hypotheses" :key="h.tokens" :class="{ inset: inSet.has(h.plate) }">
        <span class="dx-plate-text plate">{{ h.plate }}</span>
        <span class="bar" aria-hidden="true">
          <span class="fill" :style="{ transform: `scaleX(${h.probability})` }" />
        </span>
        <span class="dx-num prob">{{ probability(h.probability, 1) }}</span>
        <span v-if="inSet.has(h.plate)" class="dx-sr-only">(in this view's set)</span>
      </li>
    </ol>
    <p v-else class="dx-muted dx-small">This view proposed no plate.</p>
  </article>
</template>

<style scoped>
.view {
  display: grid;
  gap: var(--dx-space-3);
  align-content: start;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--dx-space-2);
}

.head h3 {
  font-size: var(--dx-text-md);
}

.crop {
  display: block;
  width: 100%;
  max-height: 72px;
  object-fit: contain;
  background: var(--dx-surface-sunken);
  border-radius: var(--dx-radius-s);
  border: 1px solid var(--dx-border);
}

.hyp-title {
  font-size: var(--dx-text-sm);
  font-weight: 600;
  color: var(--dx-text-muted);
}

.hyps {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.hyps li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 64px 56px;
  align-items: center;
  gap: var(--dx-space-2);
  padding: 2px 6px;
  border-radius: var(--dx-radius-s);
  font-size: var(--dx-text-sm);
}

.hyps li.inset {
  background: var(--dx-accent-soft);
}

.plate {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: var(--dx-text-md);
}

.bar {
  height: 6px;
  border-radius: 999px;
  background: var(--dx-surface-sunken);
  overflow: hidden;
}

.fill {
  display: block;
  height: 100%;
  background: var(--dx-chart-ink);
  transform-origin: left center;
}

.prob {
  text-align: right;
}
</style>
