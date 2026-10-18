<script setup lang="ts">
import { computed } from 'vue'

import { LOWER_IS_BETTER, METRIC_LABELS, PLAIN_METRICS, type Estimate } from '@/api/results'
import { estimateValue, interval } from '@/lib/format'

import CiBar from './CiBar.vue'

const props = withDefaults(
  defineProps<{
    /** Column name -> metric name -> estimate. */
    columns: Record<string, Record<string, Estimate>>
    metrics: string[]
    caption: string
    columnLabel?: (name: string) => string
  }>(),
  { columnLabel: (name: string) => name },
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
            <template v-if="columns[name]?.[metric]">
              <div class="cell">
                <strong class="dx-num">{{
                  estimateValue(columns[name]![metric]!, PLAIN_METRICS.has(metric))
                }}</strong>
                <CiBar :estimate="columns[name]![metric]!" :domain="domain(metric)" />
              </div>
              <div class="dx-num ci">
                95% CI {{ interval(columns[name]![metric]!, PLAIN_METRICS.has(metric)) }}
              </div>
            </template>
            <span v-else class="dx-muted">–</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.metrics th[scope='row'] {
  color: var(--dx-text);
  font-weight: 600;
  white-space: normal;
  min-width: 140px;
}

.hint {
  display: block;
  font-size: var(--dx-text-xs);
  font-weight: 400;
  color: var(--dx-text-muted);
}

.cell {
  display: flex;
  align-items: center;
  gap: var(--dx-space-2);
  white-space: nowrap;
}

.ci {
  font-size: var(--dx-text-xs);
  color: var(--dx-text-muted);
  white-space: nowrap;
}
</style>
