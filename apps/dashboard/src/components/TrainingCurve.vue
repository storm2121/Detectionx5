<script setup lang="ts">
import { extent, line, scaleLinear } from 'd3'
import { computed, useId } from 'vue'

import type { TrainingEpoch } from '@/api/results'
import { percent } from '@/lib/format'

/** Validation exact match by epoch: one series in the accent, the kept epoch marked. */
const props = defineProps<{ history: TrainingEpoch[]; bestEpoch?: number }>()

const id = useId()
const W = 520
const H = 220
const M = { top: 14, right: 16, bottom: 36, left: 44 }

const x = computed(() => {
  const [lo, hi] = extent(props.history, (e) => e.epoch) as [number | undefined, number | undefined]
  return scaleLinear()
    .domain([lo ?? 0, Math.max(hi ?? 1, (lo ?? 0) + 1)])
    .range([M.left, W - M.right])
})
const y = scaleLinear()
  .domain([0, 1])
  .range([H - M.bottom, M.top])

const path = computed(
  () =>
    line<TrainingEpoch>()
      .x((e) => x.value(e.epoch))
      .y((e) => y(e.val_exact_greedy))(props.history) ?? '',
)
const xTicks = computed(() => x.value.ticks(6))
const yTicks = [0, 0.25, 0.5, 0.75, 1]

// Shade the epochs of phases after the first (fine-tuning, when there is one).
const phases = computed(() => {
  const first = props.history[0]?.phase
  const spans: { phase: string; from: number; to: number }[] = []
  for (const epoch of props.history) {
    if (epoch.phase === first) continue
    const last = spans[spans.length - 1]
    if (last && last.phase === epoch.phase) last.to = epoch.epoch
    else spans.push({ phase: epoch.phase, from: epoch.epoch, to: epoch.epoch })
  }
  return spans
})
const best = computed(() => props.history.find((e) => e.epoch === props.bestEpoch) ?? null)
const caption = computed(() => {
  const base = 'Exact match on the synthetic validation split after each epoch, greedy decoding'
  const later = phases.value[0]
  return later
    ? `${base}; the shaded epochs are the ${later.phase.replace(/_/g, ' ')} phase.`
    : `${base}. The ring marks the kept epoch.`
})
</script>

<template>
  <figure class="training" data-testid="training-curve">
    <svg :viewBox="`0 0 ${W} ${H}`" role="img" :aria-labelledby="`${id}-t ${id}-d`">
      <title :id="`${id}-t`">Validation exact match by epoch</title>
      <desc :id="`${id}-d`">
        {{ history.length }} epochs on synthetic data
        <template v-if="best">
          ; kept epoch {{ best.epoch }} at {{ percent(best.val_exact_greedy, 1) }}
        </template>
        .
      </desc>
      <rect
        v-for="span in phases"
        :key="span.phase + span.from"
        class="phase"
        :x="x(span.from - 0.5)"
        :y="M.top"
        :width="x(span.to + 0.5) - x(span.from - 0.5)"
        :height="H - M.top - M.bottom"
      />
      <g class="grid" aria-hidden="true">
        <line v-for="t in yTicks" :key="t" :x1="M.left" :x2="W - M.right" :y1="y(t)" :y2="y(t)" />
      </g>
      <g class="axis" aria-hidden="true">
        <text v-for="t in yTicks" :key="`y${t}`" :x="M.left - 8" :y="y(t) + 4" text-anchor="end">
          {{ percent(t, 0) }}
        </text>
        <text
          v-for="t in xTicks"
          :key="`x${t}`"
          :x="x(t)"
          :y="H - M.bottom + 16"
          text-anchor="middle"
        >
          {{ t }}
        </text>
        <text class="label" :x="(M.left + W - M.right) / 2" :y="H - 4" text-anchor="middle">
          Epoch
        </text>
      </g>
      <path class="curve" :d="path" />
      <circle v-if="best" class="best" :cx="x(best.epoch)" :cy="y(best.val_exact_greedy)" r="5" />
    </svg>
    <figcaption class="dx-footnote dx-secondary">{{ caption }}</figcaption>
  </figure>
</template>

<style scoped>
.training {
  display: grid;
  gap: var(--dx-space-2);
  min-width: 0;
  margin: 0;
}

svg {
  width: 100%;
  height: auto;
  font-family: var(--dx-font-small);
}

.phase {
  fill: var(--dx-surface-inset);
}

.grid line {
  stroke: var(--dx-chart-grid);
}

.axis text {
  fill: var(--dx-text-2);
  font-size: 11px;
}

.axis .label {
  font-size: 12px;
  font-weight: 500;
}

.curve {
  fill: none;
  stroke: var(--dx-chart-mark);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.best {
  fill: var(--dx-surface);
  stroke: var(--dx-chart-mark);
  stroke-width: 2;
}
</style>
