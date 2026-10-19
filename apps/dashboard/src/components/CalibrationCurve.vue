<script setup lang="ts">
import { line, scaleLinear, scaleSqrt, select } from 'd3'
import { computed, onMounted, ref, useId, watch } from 'vue'

import type { ReliabilityBin } from '@/api/results'
import { percent } from '@/lib/format'
import { chartDuration, springEase } from '@/motion/springs'

/**
 * A reliability diagram: accuracy against confidence per bin, the model in the accent on a
 * neutral frame, the diagonal of perfect calibration, and under it how many reads fell in
 * each bin. When the bins change (another recogniser or set), D3 joins the new data onto the
 * same marks and moves them on the spring curve; nothing is re-mounted.
 */
const props = withDefaults(
  defineProps<{ bins: ReliabilityBin[]; title?: string; ece?: number | null }>(),
  { title: 'Reliability diagram', ece: null },
)

const id = useId()
const W = 340
const H = 300
const M = { top: 12, right: 14, bottom: 60, left: 44 }
const COUNT_H = 22

const x = scaleLinear()
  .domain([0, 1])
  .range([M.left, W - M.right])
const y = scaleLinear()
  .domain([0, 1])
  .range([H - M.bottom, M.top])
const ticks = [0, 0.25, 0.5, 0.75, 1]

const plot = ref<SVGGElement | null>(null)

type Filled = ReliabilityBin & { accuracy: number; confidence: number }
const filled = computed(() =>
  props.bins.filter((b): b is Filled => b.n > 0 && b.accuracy !== null && b.confidence !== null),
)
const total = computed(() => props.bins.reduce((sum, b) => sum + b.n, 0))
const summary = computed(() =>
  filled.value
    .map(
      (b) =>
        `${percent(b.low, 0)} to ${percent(b.high, 0)}: accuracy ${percent(b.accuracy, 1)} at mean confidence ${percent(b.confidence, 1)}, ${b.n} reads`,
    )
    .join('; '),
)

function draw(animate: boolean) {
  if (!plot.value) return
  const root = select(plot.value)
  const duration = animate ? chartDuration() : 0
  const radius = scaleSqrt()
    .domain([0, Math.max(1, ...filled.value.map((b) => b.n))])
    .range([4, 7])
  const countScale = scaleLinear()
    .domain([0, Math.max(1, ...props.bins.map((b) => b.n))])
    .range([0, COUNT_H])
  const key = (b: ReliabilityBin) => `${b.low}-${b.high}`

  // how many reads per bin: thin columns that grow from the baseline (scaleY only)
  root
    .select<SVGGElement>('.counts')
    .selectAll<SVGRectElement, ReliabilityBin>('rect')
    .data(props.bins, key)
    .join((enter) =>
      enter
        .append('rect')
        .attr('x', (b) => x(b.low) + 2)
        .attr('width', (b) => Math.max(1, x(b.high) - x(b.low) - 4))
        .attr('y', H - M.bottom + 30)
        .attr('height', COUNT_H)
        .attr('rx', 2)
        .style('transform-box', 'fill-box')
        .style('transform-origin', '50% 100%')
        .style('transform', 'scaleY(0)'),
    )
    .transition()
    .duration(duration)
    .ease(springEase)
    .style('transform', (b) => `scaleY(${countScale(b.n) / COUNT_H})`)

  // the curve: a 2px line through the points, cross-faded when the data changes
  const path = line<Filled>()
    .x((b) => x(b.confidence))
    .y((b) => y(b.accuracy))(filled.value)
  const curve = root.select<SVGPathElement>('.curve')
  if (duration > 0 && curve.attr('d')) {
    curve
      .transition()
      .duration(duration / 2)
      .style('opacity', 0)
      .transition()
      .duration(0)
      .attr('d', path ?? '')
      .transition()
      .duration(duration / 2)
      .style('opacity', 1)
  } else {
    curve.attr('d', path ?? '').style('opacity', 1)
  }

  // the points move to their new place (translate only) and are sized by their count
  root
    .select<SVGGElement>('.points')
    .selectAll<SVGCircleElement, Filled>('circle')
    .data(filled.value, key)
    .join(
      (enter) =>
        enter
          .append('circle')
          .attr('cx', 0)
          .attr('cy', 0)
          .attr('r', (b) => radius(b.n))
          .style('opacity', 0)
          .style('transform', (b) => `translate(${x(b.confidence)}px, ${y(b.accuracy)}px)`),
      (update) => update,
      (exit) => exit.transition().duration(duration).style('opacity', 0).remove(),
    )
    .attr('r', (b) => radius(b.n))
    .transition()
    .duration(duration)
    .ease(springEase)
    .style('opacity', 1)
    .style('transform', (b) => `translate(${x(b.confidence)}px, ${y(b.accuracy)}px)`)
}

onMounted(() => draw(false))
watch(
  () => props.bins,
  () => draw(true),
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
      <g class="grid" aria-hidden="true">
        <line v-for="t in ticks" :key="`h${t}`" :x1="x(0)" :x2="x(1)" :y1="y(t)" :y2="y(t)" />
        <line v-for="t in ticks" :key="`v${t}`" :x1="x(t)" :x2="x(t)" :y1="y(0)" :y2="y(1)" />
      </g>
      <g class="axis" aria-hidden="true">
        <text v-for="t in ticks" :key="`xt${t}`" :x="x(t)" :y="y(0) + 16" text-anchor="middle">
          {{ percent(t, 0) }}
        </text>
        <text v-for="t in ticks" :key="`yt${t}`" :x="x(0) - 8" :y="y(t) + 4" text-anchor="end">
          {{ percent(t, 0) }}
        </text>
        <text class="label" :x="(x(0) + x(1)) / 2" :y="y(0) + 28" text-anchor="middle">
          Confidence
        </text>
        <text
          class="label"
          :transform="`translate(11 ${(y(0) + y(1)) / 2}) rotate(-90)`"
          text-anchor="middle"
        >
          Accuracy
        </text>
      </g>
      <line class="ideal" :x1="x(0)" :y1="y(0)" :x2="x(1)" :y2="y(1)" aria-hidden="true" />
      <g ref="plot" aria-hidden="true">
        <g class="counts" />
        <path class="curve" />
        <g class="points" />
      </g>
    </svg>
    <figcaption>
      <ul class="legend" aria-label="Legend">
        <li><span class="key line" aria-hidden="true" />Accuracy at each bin's mean confidence</li>
        <li><span class="key ideal" aria-hidden="true" />Perfect calibration</li>
        <li><span class="key count" aria-hidden="true" />Reads per bin</li>
      </ul>
      <p class="dx-footnote dx-secondary">
        {{ total }} reads in ten equal-width bins; larger dots hold more reads.
        <template v-if="ece !== null">Expected calibration error {{ percent(ece, 1) }}.</template>
      </p>
    </figcaption>
  </figure>
</template>

<style scoped>
.calibration {
  display: grid;
  gap: var(--dx-space-2);
  min-width: 0;
  margin: 0;
}

svg {
  width: 100%;
  max-width: 26rem;
  height: auto;
  font-family: var(--dx-font-small);
}

.grid line {
  stroke: var(--dx-chart-grid);
  stroke-width: 1;
}

.axis text {
  fill: var(--dx-text-2);
  font-size: 11px;
}

.axis .label {
  font-size: 12px;
  font-weight: 500;
}

.ideal {
  stroke: var(--dx-chart-axis);
  stroke-width: 1;
}

:deep(.counts rect) {
  fill: var(--dx-chart-neutral);
  opacity: 0.55;
}

:deep(.curve) {
  fill: none;
  stroke: var(--dx-chart-mark);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

:deep(.points circle) {
  fill: var(--dx-chart-mark);
  stroke: var(--dx-surface);
  stroke-width: 2;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--dx-space-1) var(--dx-space-4);
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--dx-text-2);
  font-size: var(--dx-text-caption);
}

.legend li {
  display: inline-flex;
  align-items: center;
  gap: var(--dx-space-1);
}

.key {
  display: inline-block;
  width: 14px;
}

.key.line {
  height: 2px;
  background: var(--dx-chart-mark);
}

.key.ideal {
  height: 1px;
  background: var(--dx-chart-axis);
}

.key.count {
  height: 8px;
  border-radius: 2px;
  background: var(--dx-chart-neutral);
  opacity: 0.55;
}
</style>
