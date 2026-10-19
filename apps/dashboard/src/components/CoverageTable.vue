<script setup lang="ts">
import type { CoverageReport } from '@/api/results'
import { estimate, level, percent, scientific } from '@/lib/format'

/** Conformal coverage and set size per level (and per number of fused views), with intervals. */
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
          <th scope="col" class="dx-num">Threshold</th>
          <th scope="col">Coverage</th>
          <th scope="col">Mean set size</th>
          <th scope="col" class="dx-num">Single plate</th>
          <th scope="col" class="dx-num">Empty</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.key">
          <th v-if="row.views !== null" scope="row">
            {{ row.views }} {{ row.views === '1' ? 'view' : 'views' }}
          </th>
          <td>{{ level(row.report.level) }}</td>
          <td class="dx-num">
            <code>{{ scientific(row.report.threshold, 2) }}</code>
          </td>
          <td>{{ estimate(row.report.coverage) }}</td>
          <td>{{ estimate(row.report.set_size, true) }} plates</td>
          <td class="dx-num">{{ percent(row.report.singleton_rate, 1) }}</td>
          <td class="dx-num">{{ percent(row.report.empty_rate, 1) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.dx-table th,
.dx-table td {
  white-space: nowrap;
}
</style>
