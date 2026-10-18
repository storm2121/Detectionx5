<script setup lang="ts">
import { computed } from 'vue'

import type { Confusion } from '@/api/results'
import { cssVar, readableOn, sequential } from '@/lib/colors'
import { percent } from '@/lib/format'
import { useThemeStore } from '@/stores/theme'

const props = withDefaults(defineProps<{ confusion: Confusion; caption?: string }>(), {
  caption: 'Letter confusion: rows are the true letter, columns the letter read.',
})

const theme = useThemeStore()

const palette = computed(() => {
  void theme.resolved
  return sequential(cssVar('--dx-heat-low', '#f1f5f9'), cssVar('--dx-heat-high', '#0f766e'))
})

const rows = computed(() =>
  props.confusion.rows.map((label, r) => {
    const counts = props.confusion.matrix[r] ?? []
    const total = counts.reduce((a, b) => a + b, 0)
    return {
      label,
      total,
      cells: props.confusion.columns.map((column, c) => {
        const count = counts[c] ?? 0
        const rate = total > 0 ? count / total : 0
        const fill = palette.value(rate)
        return { column, count, rate, fill, ink: readableOn(fill), diagonal: column === label }
      }),
    }
  }),
)

const accuracy = computed(() => {
  let correct = 0
  let total = 0
  for (const row of rows.value) {
    total += row.total
    correct += row.cells.find((c) => c.diagonal)?.count ?? 0
  }
  return total > 0 ? correct / total : null
})

function columnLabel(column: string) {
  return column === 'none' ? 'none read' : column
}
</script>

<template>
  <div
    class="confusion dx-scroll-x"
    role="region"
    aria-label="Letter confusion matrix"
    tabindex="0"
    data-testid="confusion-matrix"
  >
    <table>
      <caption>
        {{
          caption
        }}
        <template v-if="accuracy !== null"> Letter accuracy {{ percent(accuracy, 1) }}.</template>
      </caption>
      <thead>
        <tr>
          <th scope="col" class="corner">True \ read</th>
          <th
            v-for="column in confusion.columns"
            :key="column"
            scope="col"
            class="col"
            :class="{ none: column === 'none' }"
          >
            <span :lang="column === 'none' ? undefined : 'ar'">{{ columnLabel(column) }}</span>
          </th>
          <th scope="col" class="col">n</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.label">
          <th scope="row" class="rowhead">
            <span lang="ar">{{ row.label }}</span>
          </th>
          <td
            v-for="cell in row.cells"
            :key="cell.column"
            :style="{ background: cell.fill, color: cell.ink }"
            :class="{ diagonal: cell.diagonal }"
            :title="`${row.label} read as ${columnLabel(cell.column)}: ${cell.count} (${percent(cell.rate, 1)})`"
          >
            {{ cell.count }}
          </td>
          <td class="total">{{ row.total }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.confusion {
  min-width: 0;
}

table {
  border-collapse: separate;
  border-spacing: 3px;
  font-variant-numeric: tabular-nums;
  font-size: var(--dx-text-sm);
}

caption {
  text-align: left;
  color: var(--dx-text-muted);
  padding-bottom: var(--dx-space-2);
  font-size: var(--dx-text-sm);
}

th {
  font-weight: 600;
  color: var(--dx-text-muted);
  padding: 2px 6px;
}

.col,
.rowhead {
  font-family: var(--dx-font-plate);
  font-size: var(--dx-text-lg);
  color: var(--dx-text);
}

.col.none {
  font-family: var(--dx-font-sans);
  font-size: var(--dx-text-xs);
  color: var(--dx-text-muted);
  white-space: nowrap;
}

.corner {
  font-size: var(--dx-text-xs);
  white-space: nowrap;
}

td {
  min-width: 40px;
  height: 34px;
  text-align: center;
  border-radius: 4px;
  font-weight: 600;
}

td.diagonal {
  box-shadow: inset 0 0 0 2px var(--dx-text);
}

td.total {
  background: transparent;
  color: var(--dx-text-muted);
  font-weight: 500;
}
</style>
