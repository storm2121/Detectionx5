<script setup lang="ts">
import type { CoverageReport } from '@/api/results'
import { fixed, interval, level, percent, scientific } from '@/lib/format'

defineProps<{
  rows: { key: string; views: string | null; report: CoverageReport }[]
  caption: string
}>()
</script>

<template>
  <div
    class="dx-scroll-x"
    role="region"
    :aria-label="caption"
    tabindex="0"
    data-testid="coverage-table"
  >
    <table class="dx-table">
      <caption>
        {{
          caption
        }}
      </caption>
      <thead>
        <tr>
          <th v-if="rows.some((r) => r.views !== null)" scope="col">Views</th>
          <th scope="col">Level</th>
          <th scope="col" class="dx-right">Threshold</th>
          <th scope="col">Coverage (95% CI)</th>
          <th scope="col">Mean set size (95% CI)</th>
          <th scope="col" class="dx-right">Singletons</th>
          <th scope="col" class="dx-right">Empty</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.key">
          <th v-if="row.views !== null" scope="row" class="dx-num">{{ row.views }}</th>
          <td class="dx-num">{{ level(row.report.level) }}</td>
          <td class="dx-right dx-num">
            <code>{{ scientific(row.report.threshold, 2) }}</code>
          </td>
          <td class="dx-num">
            <strong>{{ percent(row.report.coverage.value, 1) }}</strong>
            <span class="dx-muted dx-ci">{{ interval(row.report.coverage) }}</span>
          </td>
          <td class="dx-num">
            <strong>{{ fixed(row.report.set_size.value, 2) }}</strong>
            <span class="dx-muted dx-ci">{{ interval(row.report.set_size, true) }}</span>
          </td>
          <td class="dx-right dx-num">{{ percent(row.report.singleton_rate, 1) }}</td>
          <td class="dx-right dx-num">{{ percent(row.report.empty_rate, 1) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
