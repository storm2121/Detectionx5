<script setup lang="ts">
import { scaleLinear, select } from 'd3'
import { computed, onMounted, ref, useId, watch } from 'vue'

import type { Estimate, EvalResult } from '@/api/results'
import { estimate } from '@/lib/format'
import { recognizerLabel } from '@/lib/labels'
import { chartDuration, springEase } from '@/motion/springs'

/**
 * The sim-to-real gap: for every recogniser, exact match on the synthetic test set and on
 * the labelled real photos, as two bars with their intervals, each labelled with the set it
 * comes from. The table comes first; the chart draws the same numbers. Synthetic bars are
 * neutral and real ones carry the accent, since the real figure is the one that matters.
 */
const props = defineProps<{
  synthetic: EvalResult
  real: EvalResult | null
  pseudoReal?: EvalResult | null
  metric?: string
}>()

const id = useId()
const metric = computed(() => props.metric ?? 'exact_match')
const plot = ref<SVGGElement | null>(null)

interface Row {
  name: string
  synthetic: Estimate | null
  real: Estimate | null
  pseudoReal: Estimate | null
}

const rows = computed<Row[]>(() =>
  Object.keys(props.synthetic.recognizers)
    .filter((name) => !props.real || name in props.real.recognizers)
    .map((name) => ({
      name,
      synthetic: props.synthetic.recognizers[name]?.metrics[metric.value] ?? null,
      real: props.real?.recognizers[name]?.metrics[metric.value] ?? null,
      pseudoReal: props.pseudoReal?.recognizers[name]?.metrics[metric.value] ?? null,
    })),
)
const nSynthetic = computed(() => props.synthetic.set.n)
const nReal = computed(() => props.real?.set.n ?? null)

const W = 640
const LABEL = 178
const BAR = 12
const PAIR = 52
const M = { top: 8, right: 16, bottom: 28 }
const height = computed(() => M.top + rows.value.length * PAIR + M.bottom)
// room on the right for each bar's label: its value, interval and set
const x = scaleLinear()
  .domain([0, 1])
  .range([LABEL, W - M.right - 190])
const ticks = [0, 0.25, 0.5, 0.75, 1]

function gap(row: Row): string {
  if (!row.synthetic || !row.real) return '–'
  const points = Math.round((row.synthetic.value - row.real.value) * 100)
  return points === 0
    ? 'none'
    : `${points} points ${points > 0 ? 'lower' : 'higher'} on real photos`
}

interface Bar {
  key: string
  kind: 'synthetic' | 'real'
  row: number
  value: Estimate
}

function draw(animate: boolean) {
  if (!plot.value) return
  const duration = animate ? chartDuration() : 0
  const bars: Bar[] = rows.value.flatMap((row, i) => [
    ...(row.synthetic
      ? [{ key: `${row.name}-s`, kind: 'synthetic' as const, row: i, value: row.synthetic }]
      : []),
    ...(row.real ? [{ key: `${row.name}-r`, kind: 'real' as const, row: i, value: row.real }] : []),
  ])
  const top = (b: Bar) => M.top + b.row * PAIR + (b.kind === 'synthetic' ? 8 : 26)
  const width = x(1) - x(0)
  const groups = select(plot.value)
    .selectAll<SVGGElement, Bar>('g.bar')
    .data(bars, (b) => b.key)
    .join((enter) => {
      const g = enter.append('g').attr('class', (b) => `bar ${b.kind}`)
      g.append('rect')
        .attr('class', 'fill')
        .attr('x', x(0))
        .attr('height', BAR)
        .attr('width', width)
        .attr('rx', 3)
        .style('transform-box', 'fill-box')
        .style('transform-origin', '0 50%')
        .style('transform', 'scaleX(0)')
      g.append('text')
        .attr('class', 'tip')
        .attr('y', BAR - 2)
      g.append('rect')
        .attr('class', 'whisker')
        .attr('x', x(0))
        .attr('height', 2)
        .attr('width', width)
        .style('transform-box', 'fill-box')
        .style('transform-origin', '0 50%')
        .style('transform', 'scaleX(0)')
      return g
    })
  groups.attr('transform', (b) => `translate(0 ${top(b)})`)
  groups
    .select<SVGTextElement>('text.tip')
    .text(
      (b) => `${estimate(b.value, false, 0)} ${b.kind === 'real' ? 'real photos' : 'synthetic'}`,
    )
    .transition()
    .duration(duration)
    .ease(springEase)
    .style('transform', (b) => `translateX(${x(b.value.ci_high) + 6}px)`)
  groups
    .select<SVGRectElement>('rect.fill')
    .transition()
    .duration(duration)
    .ease(springEase)
    .style('transform', (b) => `scaleX(${Math.max(0.002, b.value.value)})`)
  groups
    .select<SVGRectElement>('rect.whisker')
    .attr('y', BAR / 2 - 1)
    .transition()
    .duration(duration)
    .ease(springEase)
    .style(
      'transform',
      (b) =>
        `translateX(${(x(b.value.ci_low) - x(0)) * 1}px) scaleX(${Math.max(0.004, b.value.ci_high - b.value.ci_low)})`,
    )
}

onMounted(() => draw(false))
watch(rows, () => draw(true))
</script>

<template>
  <div class="gap" data-testid="sim-to-real">
    <div class="dx-scroll-x" role="region" aria-label="Sim-to-real gap" tabindex="0">
      <table class="dx-table">
        <caption>
          Exact match of each recogniser on the synthetic test set and on the labelled plates of the
          real photos, read from their labelled boxes, with 95% bootstrap intervals.
        </caption>
        <thead>
          <tr>
            <th scope="col">Recogniser</th>
            <th scope="col">Synthetic test set (n = {{ nSynthetic }})</th>
            <th scope="col">
              Real plates<template v-if="nReal"> (n = {{ nReal }})</template>
            </th>
            <th v-if="pseudoReal" scope="col">Pseudo-real set (n = {{ pseudoReal.set.n }})</th>
            <th scope="col">Gap</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.name">
            <th scope="row">{{ recognizerLabel(row.name) }}</th>
            <td>{{ row.synthetic ? estimate(row.synthetic, false, 0) : '–' }}</td>
            <td>{{ row.real ? estimate(row.real, false, 0) : 'not measured' }}</td>
            <td v-if="pseudoReal">
              {{ row.pseudoReal ? estimate(row.pseudoReal, false, 0) : '–' }}
            </td>
            <td>{{ gap(row) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <figure class="chart">
      <svg :viewBox="`0 0 ${W} ${height}`" role="img" :aria-labelledby="`${id}-t ${id}-d`">
        <title :id="`${id}-t`">Exact match on synthetic plates and on real photos</title>
        <desc :id="`${id}-d`">
          <template v-for="row in rows" :key="row.name">
            {{ recognizerLabel(row.name) }}: synthetic
            {{ row.synthetic ? estimate(row.synthetic, false, 0) : 'not measured' }}, real
            {{ row.real ? estimate(row.real, false, 0) : 'not measured' }}.
          </template>
        </desc>
        <g class="grid" aria-hidden="true">
          <line
            v-for="t in ticks"
            :key="t"
            :x1="x(t)"
            :x2="x(t)"
            :y1="M.top"
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
        <g aria-hidden="true">
          <g v-for="(row, i) in rows" :key="row.name">
            <text class="name" :x="0" :y="M.top + i * PAIR + 28">
              {{ recognizerLabel(row.name) }}
            </text>
          </g>
        </g>
        <g ref="plot" aria-hidden="true" />
      </svg>
      <figcaption>
        <ul class="legend" aria-label="Legend">
          <li>
            <span class="key synthetic" aria-hidden="true" />Synthetic test set, n =
            {{ nSynthetic }}
          </li>
          <li v-if="nReal">
            <span class="key real" aria-hidden="true" />Real plates, n = {{ nReal }}
          </li>
          <li><span class="key whisker" aria-hidden="true" />95% interval</li>
        </ul>
        <p class="dx-footnote dx-secondary">
          Synthetic results are not real-world accuracy: the synthetic bars are the development
          harness's, shown to measure the gap.
        </p>
      </figcaption>
    </figure>
  </div>
</template>

<style scoped>
.gap {
  display: grid;
  gap: var(--dx-space-5);
  min-width: 0;
}

.chart {
  display: grid;
  gap: var(--dx-space-2);
  min-width: 0;
  margin: 0;
}

svg {
  width: 100%;
  max-width: 44rem;
  height: auto;
  font-family: var(--dx-font-small);
}

.grid line {
  stroke: var(--dx-chart-grid);
}

.grid text {
  fill: var(--dx-text-2);
  font-size: 11px;
}

.name {
  fill: var(--dx-text);
  font-size: 13px;
  font-weight: 500;
}

:deep(.bar .tip) {
  fill: var(--dx-text-2);
  font-size: 11px;
}

:deep(.bar.synthetic .fill) {
  fill: var(--dx-chart-neutral);
}

:deep(.bar.real .fill) {
  fill: var(--dx-chart-mark);
}

:deep(.bar .whisker) {
  fill: var(--dx-text);
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
  height: 10px;
  border-radius: 2px;
}

.key.synthetic {
  background: var(--dx-chart-neutral);
}

.key.real {
  background: var(--dx-chart-mark);
}

.key.whisker {
  height: 2px;
  background: var(--dx-text);
}
</style>
