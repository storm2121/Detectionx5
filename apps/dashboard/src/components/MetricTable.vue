<script setup lang="ts">
import { computed } from 'vue'

import { LOWER_IS_BETTER, METRIC_LABELS, PLAIN_METRICS, type Estimate } from '@/api/results'
import { estimate } from '@/lib/format'

import CiBar from './CiBar.vue'

/**
 * Metrics by recogniser, every value with its interval in words, `25% (0 to 50)`, at one
 * precision for the whole table, and the interval drawn beside it. Rows are metrics, columns
 * recognisers, so a reader compares across a row.
 */
const props = withDefaults(
  defineProps<{
    /** Column name -> metric name -> estimate. */
    columns: Record<string, Record<string, Estimate>>
    metrics: string[]
    caption: string
    columnLabel?: (name: string) => string
    /** Decimals of the percentages; whole numbers suit a small set. */
    digits?: number
  }>(),
  { columnLabel: (name: string) => name, digits: 1 },
)

const names = computed(() => Object.keys(props.columns))
const visible = computed(() =>
  props.metrics.filter((m) => names.value.some((n) => props.columns[n]?.[m] !== undefined)),
)

function domain(metric: string): [number, number] {
  if (!PLAIN_METRICS.has(metric)) return [0, 1]
  const highs = names.value.map((n) => props.columns[n]?.[metric]?.ci_high ?? 0)
  return [0, Math.max(1, ...highs)]
}
</script>

<template>
  <div
    class="dx-scroll-x"
    role="region"
    :aria-label="caption"
    tabindex="0"
    data-testid="metric-table"
  >
    <table class="dx-table metrics">
      <caption>
        {{
          caption
        }}
      </caption>
      <thead>
        <tr>
          <th scope="col">Metric</th>
          <th v-for="name in names" :key="name" scope="col">{{ columnLabel(name) }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="metric in visible" :key="metric">
          <th scope="row">
            {{ METRIC_LABELS[metric] ?? metric }}
            <span v-if="LOWER_IS_BETTER.has(metric)" class="hint">lower is better</span>
          </th>
          <td v-for="name in names" :key="name">
            <span v-if="columns[name]?.[metric]" class="cell">
              <span class="value">{{
                estimate(columns[name]![metric]!, PLAIN_METRICS.has(metric), digits)
              }}</span>
              <CiBar :estimate="columns[name]![metric]!" :domain="domain(metric)" />
            </span>
            <span v-else class="dx-tertiary">–</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="dx-sr-only">Each value is followed by its 95% bootstrap interval in brackets.</p>
  </div>
</template>

<style scoped>
.metrics th[scope='row'] {
  min-width: 9rem;
  white-space: normal;
}

.hint {
  display: block;
  color: var(--dx-text-2);
  font-family: var(--dx-font-small);
  font-size: var(--dx-text-caption);
  font-weight: var(--dx-weight-body);
}

.cell {
  display: inline-flex;
  align-items: center;
  gap: var(--dx-space-3);
  white-space: nowrap;
}

.value {
  min-width: 8.5rem;
}
</style>
