<script setup lang="ts">
import { computed } from 'vue'

import type { ReadOut } from '@/api/types'
import { probability } from '@/lib/format'
import { fusionRows } from '@/lib/fusion'
import { fusionLabel } from '@/lib/labels'

/**
 * Each view's probability for every candidate it proposed, beside the fused posterior.
 * `order` lists the views in the order the tray shows them; fusion does not depend on it.
 */
const props = withDefaults(
  defineProps<{ read: ReadOut; order?: number[] | null; limit?: number }>(),
  {
    order: null,
    limit: 8,
  },
)

const rows = computed(() => fusionRows(props.read, props.limit))
const columns = computed(() => props.order ?? props.read.views.map((_, i) => i))
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
        Each view's probability for the candidates it proposed, and the fused posterior ({{
          fusionLabel(read.fusion).toLowerCase()
        }}). A dash: that view did not propose it.
      </caption>
      <thead>
        <tr>
          <th scope="col">Candidate</th>
          <th v-for="(view, n) in columns" :key="view" scope="col" class="dx-num">
            View {{ n + 1 }}
          </th>
          <th scope="col" class="dx-num">Fused</th>
          <th scope="col">Set</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.tokens" :class="{ top: row.isPrediction }">
          <th scope="row">
            <span class="dx-plate">{{ row.plate }}</span>
            <span v-if="row.isPrediction" class="dx-sr-only"> (the read)</span>
          </th>
          <td v-for="view in columns" :key="view" class="dx-num">
            {{
              row.views[view] === null || row.views[view] === undefined
                ? '–'
                : probability(row.views[view], 1)
            }}
          </td>
          <td class="dx-num fused">{{ probability(row.fused, 1) }}</td>
          <td>
            <span v-if="row.inSet" class="in-set">in set</span>
            <span v-else class="dx-tertiary">–</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
tr.top > * {
  background: var(--dx-accent-soft);
}

tr.top > :first-child {
  padding-left: var(--dx-space-2);
  border-radius: var(--dx-radius-control) 0 0 var(--dx-radius-control);
}

tr.top > :last-child {
  border-radius: 0 var(--dx-radius-control) var(--dx-radius-control) 0;
}

.fused {
  font-weight: var(--dx-weight-title);
}

.in-set {
  color: var(--dx-success);
  font-weight: var(--dx-weight-label);
}
</style>
