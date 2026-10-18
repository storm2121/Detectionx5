<script setup lang="ts">
import { scaleLinear, scaleSqrt } from 'd3'
import { computed, useId } from 'vue'

import type { ReliabilityBin } from '@/api/results'
import { percent } from '@/lib/format'

const props = withDefaults(
  defineProps<{ bins: ReliabilityBin[]; title?: string; ece?: number | null }>(),
  { title: 'Reliability diagram', ece: null },
)

const id = useId()
const W = 320
const H = 280
const M = { top: 12, right: 12, bottom: 40, left: 46 }

const x = scaleLinear()
  .domain([0, 1])
  .range([M.left, W - M.right])
const y = scaleLinear()
  .domain([0, 1])
  .range([H - M.bottom, M.top])
const ticks = [0, 0.25, 0.5, 0.75, 1]

const filled = computed(() =>
  props.bins.filter(
    (b): b is ReliabilityBin & { accuracy: number; confidence: number } =>
      b.n > 0 && b.accuracy !== null && b.confidence !== null,
  ),
)
const total = computed(() => props.bins.reduce((sum, b) => sum + b.n, 0))
const radius = computed(() =>
  scaleSqrt()
    .domain([0, Math.max(1, ...filled.value.map((b) => b.n))])
    .range([0, 5]),
)

const bars = computed(() =>
  filled.value.map((b) => {
    const top = Math.min(b.accuracy, b.confidence)
    const bottom = Math.max(b.accuracy, b.confidence)
    return {
      key: `${b.low}-${b.high}`,
      x: x(b.low) + 1.5,
      width: Math.max(1, x(b.high) - x(b.low) - 3),
      barY: y(b.accuracy),
      barHeight: y(0) - y(b.accuracy),
      gapY: y(bottom),
      gapHeight: Math.max(0, y(top) - y(bottom)),
      cx: x(b.confidence),
      cy: y(b.accuracy),
      r: Math.max(2.5, radius.value(b.n)),
      bin: b,
    }
  }),
)

const summary = computed(() =>
  filled.value
    .map(
      (b) =>
        `${percent(b.low, 0)} to ${percent(b.high, 0)}: accuracy ${percent(b.accuracy, 1)}, confidence ${percent(b.confidence, 1)}, ${b.n} reads`,
    )
    .join('; '),
)
</script>

<template>
  <figure class="calibration" data-testid="calibration-curve">
    <svg
      :viewBox="`0 0 ${W} ${H}`"
      role="img"
      :aria-labelledby="`${id}-t ${id}-d`"
      preserveAspectRatio="xMidYMid meet"
    >
      <title :id="`${id}-t`">{{ title }}</title>
      <desc :id="`${id}-d`">{{ summary || 'No reads in any bin.' }}</desc>
      <defs>
        <pattern
          :id="`${id}-gap`"
          width="6"
          height="6"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <rect width="6" height="6" class="gap-bg" />
          <line x1="0" y1="0" x2="0" y2="6" class="gap-line" />
        </pattern>
      </defs>
      <g class="grid">
        <line v-for="t in ticks" :key="`h${t}`" :x1="x(0)" :x2="x(1)" :y1="y(t)" :y2="y(t)" />
        <line v-for="t in ticks" :key="`v${t}`" :x1="x(t)" :x2="x(t)" :y1="y(0)" :y2="y(1)" />
      </g>
      <g class="axis">
        <text v-for="t in ticks" :key="`xt${t}`" :x="x(t)" :y="y(0) + 16" text-anchor="middle">
          {{ t }}
        </text>
        <text v-for="t in ticks" :key="`yt${t}`" :x="x(0) - 8" :y="y(t) + 4" text-anchor="end">
          {{ t }}
        </text>
        <text class="label" :x="(x(0) + x(1)) / 2" :y="H - 6" text-anchor="middle">Confidence</text>
        <text
          class="label"
          :transform="`translate(12 ${(y(0) + y(1)) / 2}) rotate(-90)`"
          text-anchor="middle"
        >
          Accuracy
        </text>
      </g>
      <line class="ideal" :x1="x(0)" :y1="y(0)" :x2="x(1)" :y2="y(1)" />
      <g v-for="bar in bars" :key="bar.key">
        <rect class="bar" :x="bar.x" :y="bar.barY" :width="bar.width" :height="bar.barHeight" />
        <rect
          class="gap"
          :x="bar.x"
          :y="bar.gapY"
          :width="bar.width"
          :height="bar.gapHeight"
          :fill="`url(#${id}-gap)`"
        />
        <circle class="point" :cx="bar.cx" :cy="bar.cy" :r="bar.r">
          <title>
            {{ percent(bar.bin.low, 0) }}–{{ percent(bar.bin.high, 0) }}: accuracy
            {{ percent(bar.bin.accuracy, 1) }}, mean confidence
            {{ percent(bar.bin.confidence, 1) }} ({{ bar.bin.n }} reads)
          </title>
        </circle>
      </g>
    </svg>
    <figcaption>
      <ul class="legend" aria-label="Legend">
        <li><span class="swatch bar" aria-hidden="true" />Accuracy per confidence bin</li>
        <li><span class="swatch gap" aria-hidden="true" />Gap to the bin's mean confidence</li>
        <li><span class="swatch ideal" aria-hidden="true" />Perfect calibration</li>
      </ul>
      <p class="dx-small dx-muted">
        {{ total }} reads in ten equal-width bins; dots sit at each bin's mean confidence, sized by
        its count.
        <template v-if="ece !== null">Expected calibration error {{ percent(ece, 2) }}.</template>
      </p>
    </figcaption>
  </figure>
</template>

<style scoped>
.calibration {
  margin: 0;
  display: grid;
  gap: var(--dx-space-2);
  min-width: 0;
}

svg {
  width: 100%;
  max-width: 420px;
  height: auto;
  font-family: var(--dx-font-sans);
}

.grid line {
  stroke: var(--dx-chart-grid);
  stroke-width: 1;
}

.axis text {
  font-size: 11px;
  fill: var(--dx-text-muted);
}

.axis .label {
  font-size: 12px;
  font-weight: 600;
}

.ideal {
  stroke: var(--dx-chart-ideal);
  stroke-width: 1.5;
  stroke-dasharray: 5 4;
}

.bar {
  fill: color-mix(in srgb, var(--dx-chart-ink) 55%, transparent);
}

.gap {
  stroke: var(--dx-chart-gap);
  stroke-width: 1.25;
}

.gap-bg {
  fill: color-mix(in srgb, var(--dx-chart-gap) 18%, var(--dx-surface));
}

.gap-line {
  stroke: var(--dx-chart-gap);
  stroke-width: 2.5;
}

.point {
  fill: var(--dx-chart-ink);
  stroke: var(--dx-surface);
  stroke-width: 1.5;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--dx-space-1) var(--dx-space-4);
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

.swatch {
  width: 14px;
  height: 10px;
  border-radius: 2px;
}

.swatch.bar {
  background: color-mix(in srgb, var(--dx-chart-ink) 55%, transparent);
}

.swatch.gap {
  border: 1.25px solid var(--dx-chart-gap);
  background: repeating-linear-gradient(
    45deg,
    var(--dx-chart-gap) 0 2px,
    color-mix(in srgb, var(--dx-chart-gap) 18%, var(--dx-surface)) 2px 5px
  );
}

.swatch.ideal {
  height: 0;
  border-top: 2px dashed var(--dx-chart-ideal);
}
</style>
