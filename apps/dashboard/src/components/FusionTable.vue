<script setup lang="ts">
import { computed } from 'vue'

import type { ReadOut } from '@/api/types'
import { probability } from '@/lib/format'
import { fusionRows } from '@/lib/fusion'

const props = withDefaults(defineProps<{ read: ReadOut; limit?: number }>(), { limit: 8 })

const rows = computed(() => fusionRows(props.read, props.limit))
const views = computed(() => props.read.views)
</script>

<template>
  <div
    class="dx-scroll-x"
    role="region"
    aria-label="Fusion table"
    tabindex="0"
    data-testid="fusion-table"
  >
    <table class="dx-table">
      <caption>
        Each view's probability for every candidate it proposed, and the fused posterior (method
        <code>{{ read.fusion }}</code
        >). A dash: the view did not propose that plate.
      </caption>
      <thead>
        <tr>
          <th scope="col">Candidate</th>
          <th v-for="view in views" :key="view.index" scope="col" class="dx-right">
            View {{ view.index + 1 }}
          </th>
          <th scope="col" class="dx-right">Fused</th>
          <th scope="col">In set</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.tokens" :class="{ top: row.isPrediction }">
          <th scope="row">
            <span class="dx-plate-text">{{ row.plate }}</span>
            <span v-if="row.isPrediction" class="dx-sr-only"> (the read)</span>
          </th>
          <td v-for="(p, i) in row.views" :key="i" class="dx-right dx-num">
            {{ p === null ? '–' : probability(p, 1) }}
          </td>
          <td class="dx-right dx-num fused">{{ probability(row.fused, 2) }}</td>
          <td>
            <span v-if="row.inSet" class="in-set">in set</span>
            <span v-else class="dx-muted">–</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
tr.top th,
tr.top td {
  background: var(--dx-accent-soft);
}

.fused {
  font-weight: 650;
}

.in-set {
  color: var(--dx-ok);
  font-weight: 600;
}

code {
  font-size: var(--dx-text-xs);
}
</style>
