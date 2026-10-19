<script setup lang="ts">
import { scaleLinear } from 'd3'
import { computed, useId } from 'vue'

import type { EvalResult, Estimate } from '@/api/results'
import { interval, percent } from '@/lib/format'
import { recognizerLabel } from '@/lib/labels'

const props = defineProps<{
  synthetic: EvalResult
  pseudoReal: EvalResult
  real?: EvalResult | null
  metric?: string
}>()

const id = useId()
const metric = computed(() => props.metric ?? 'exact_match')

interface Row {
  name: string
  synthetic: Estimate | null
  pseudoReal: Estimate | null
  real: Estimate | null
}

const rows = computed<Row[]>(() =>
  Object.keys(props.synthetic.recognizers).map((name) => ({
    name,
    synthetic: props.synthetic.recognizers[name]?.metrics[metric.value] ?? null,
    pseudoReal: props.pseudoReal.recognizers[name]?.metrics[metric.value] ?? null,
    real: props.real?.recognizers[name]?.metrics[metric.value] ?? null,
  })),
)

const W = 560
const ROW = 34
const M = { top: 24, right: 20, bottom: 30, left: 190 }
const height = computed(() => M.top + rows.value.length * ROW + M.bottom)
const x = scaleLinear()
  .domain([0, 1])
  .range([M.left, W - M.right])
const ticks = [0, 0.25, 0.5, 0.75, 1]

function gap(row: Row): number | null {
  if (!row.synthetic || !row.pseudoReal) return null
  return row.pseudoReal.value - row.synthetic.value
}
</script>

<template>
  <figure class="gap-chart" data-testid="sim-to-real">
    <svg :viewBox="`0 0 ${W} ${height}`" role="img" :aria-labelledby="`${id}-t ${id}-d`">
      <title :id="`${id}-t`">Exact match on synthetic versus pseudo-real plates</title>
      <desc :id="`${id}-d`">
        <template v-for="row in rows" :key="row.name">
          {{ recognizerLabel(row.name) }}: synthetic {{ percent(row.synthetic?.value, 1) }},
          pseudo-real {{ percent(row.pseudoReal?.value, 1) }}.
        </template>
      </desc>
      <g class="grid">
        <line
          v-for="t in ticks"
          :key="t"
          :x1="x(t)"
          :x2="x(t)"
          :y1="M.top - 8"
          :y2="height - M.bottom"
        />
        <text
          v-for="t in ticks"
          :key="`l${t}`"
          :x="x(t)"
          :y="height - M.bottom + 16"
          text-anchor="middle"
        >
          {{ Math.round(t * 100) }}%
        </text>
      </g>
      <g
        v-for="(row, i) in rows"
        :key="row.name"
        :transform="`translate(0 ${M.top + i * ROW + ROW / 2})`"
      >
        <text class="name" :x="M.left - 12" y="4" text-anchor="end">
          {{ recognizerLabel(row.name) }}
        </text>
        <line
          v-if="row.synthetic && row.pseudoReal"
          class="link"
          :x1="x(row.pseudoReal.value)"
          :x2="x(row.synthetic.value)"
          y1="0"
          y2="0"
        />
        <g v-if="row.pseudoReal" class="pseudo">
          <line :x1="x(row.pseudoReal.ci_low)" :x2="x(row.pseudoReal.ci_high)" y1="0" y2="0" />
          <circle :cx="x(row.pseudoReal.value)" cy="0" r="6" />
        </g>
        <g v-if="row.synthetic" class="synthetic">
          <line :x1="x(row.synthetic.ci_low)" :x2="x(row.synthetic.ci_high)" y1="0" y2="0" />
          <circle :cx="x(row.synthetic.value)" cy="0" r="6" />
        </g>
      </g>
    </svg>
    <ul class="legend" aria-label="Legend">
      <li><span class="dot synthetic" aria-hidden="true" />synthetic test set</li>
      <li><span class="dot pseudo" aria-hidden="true" />pseudo-real set</li>
      <li class="dx-muted">real photos: {{ real ? 'measured' : 'no labelled set yet' }}</li>
    </ul>
    <div class="dx-scroll-x" role="region" aria-label="Sim-to-real gap" tabindex="0">
      <table class="dx-table">
        <thead>
          <tr>
            <th scope="col">Recogniser</th>
            <th scope="col">Synthetic</th>
            <th scope="col">Pseudo-real</th>
            <th scope="col">Real</th>
            <th scope="col" class="dx-right">Gap</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.name">
            <th scope="row">{{ recognizerLabel(row.name) }}</th>
            <td class="dx-num">
              {{ percent(row.synthetic?.value, 1) }}
              <span v-if="row.synthetic" class="dx-muted dx-ci">{{ interval(row.synthetic) }}</span>
            </td>
            <td class="dx-num">
              {{ percent(row.pseudoReal?.value, 1) }}
              <span v-if="row.pseudoReal" class="dx-muted dx-ci">{{
                interval(row.pseudoReal)
              }}</span>
            </td>
            <td class="dx-muted">{{ row.real ? percent(row.real.value, 1) : 'not measured' }}</td>
            <td class="dx-right dx-num">
              {{ gap(row) === null ? '–' : `${((gap(row) ?? 0) * 100).toFixed(1)} points` }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </figure>
</template>

<style scoped>
.gap-chart {
  margin: 0;
  display: grid;
  gap: var(--dx-space-3);
  min-width: 0;
}

svg {
  width: 100%;
  height: auto;
  font-family: var(--dx-font-sans);
}

.grid line {
  stroke: var(--dx-chart-grid);
}

.grid text {
  font-size: 11px;
  fill: var(--dx-text-muted);
}

.name {
  font-size: 12px;
  fill: var(--dx-text);
}

.link {
  stroke: var(--dx-border-strong);
  stroke-width: 3;
}

.synthetic line,
.pseudo line {
  stroke-width: 2;
}

.synthetic line {
  stroke: var(--dx-chart-ink);
}

.synthetic circle {
  fill: var(--dx-chart-ink);
}

.pseudo line {
  stroke: var(--dx-chart-gap);
}

.pseudo circle {
  fill: var(--dx-surface);
  stroke: var(--dx-chart-gap);
  stroke-width: 2.5;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--dx-space-2) var(--dx-space-4);
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: var(--dx-text-xs);
  color: var(--dx-text-muted);
}

.legend li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot.synthetic {
  background: var(--dx-chart-ink);
}

.dot.pseudo {
  border: 2px solid var(--dx-chart-gap);
}
</style>
