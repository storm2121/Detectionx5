<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import type { Confusion } from '@/api/results'
import { inkFor, tokenOn } from '@/lib/colors'
import { percent } from '@/lib/format'
import { rampOpacity } from '@/lib/readout'
import { useThemeStore } from '@/stores/theme'

/**
 * Letter confusions as a table: rows are the true letter, columns the letter read, each cell
 * the count over a one-hue ramp from the surface to the accent (the overlay's opacity is the
 * square root of the row's share). A new matrix fades each cell to its new intensity in place.
 */
const props = withDefaults(defineProps<{ confusion: Confusion; caption?: string }>(), {
  caption: 'Letter confusion: rows are the true letter, columns the letter read.',
})

const theme = useThemeStore()
const root = ref<HTMLElement | null>(null)
const ramp = ref({ low: '#f0f0f3', high: '#0066cc' })

function readTokens() {
  ramp.value = {
    low: tokenOn(root.value, '--dx-ramp-low', ramp.value.low),
    high: tokenOn(root.value, '--dx-ramp-high', ramp.value.high),
  }
}

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
        const alpha = rampOpacity(rate)
        const ink = inkFor(ramp.value.low, ramp.value.high, alpha) === 'light'
        return { column, count, rate, alpha, ink, diagonal: column === label }
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

onMounted(readTokens)
watch(
  () => theme.resolved,
  () => void nextTick(readTokens),
)
</script>

<template>
  <div
    ref="root"
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
          <th scope="col" class="col total-head">Reads</th>
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
            :class="{ diagonal: cell.diagonal, light: cell.ink }"
            :title="`${row.label} read as ${columnLabel(cell.column)}: ${cell.count} (${percent(cell.rate, 1)})`"
          >
            <span class="fill" :style="{ opacity: cell.alpha }" aria-hidden="true" />
            <span class="count">{{ cell.count }}</span>
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
  font-size: var(--dx-text-dense);
}

caption {
  padding-bottom: var(--dx-space-2);
  color: var(--dx-text-2);
  font-size: var(--dx-text-footnote);
  text-align: left;
}

th {
  padding: 2px 6px;
  color: var(--dx-text-2);
  font-weight: var(--dx-weight-label);
}

.col,
.rowhead {
  color: var(--dx-text);
  font-size: var(--dx-text-headline);
}

.col.none,
.total-head {
  color: var(--dx-text-2);
  font-family: var(--dx-font-small);
  font-size: var(--dx-text-caption);
  white-space: nowrap;
}

.corner {
  font-family: var(--dx-font-small);
  font-size: var(--dx-text-caption);
  white-space: nowrap;
}

td {
  position: relative;
  min-width: 2.5rem;
  height: 2.125rem;
  overflow: hidden;
  border-radius: 4px;
  background: var(--dx-ramp-low);
  color: var(--dx-ink-dark);
  font-weight: var(--dx-weight-label);
  text-align: center;
}

td.light {
  color: var(--dx-ink-light);
}

.fill {
  position: absolute;
  inset: 0;
  background: var(--dx-ramp-high);
  transition: opacity 450ms cubic-bezier(0.25, 0.1, 0.1, 1);
}

.count {
  position: relative;
}

td.diagonal {
  box-shadow: inset 0 0 0 1.5px var(--dx-text);
}

td.total {
  background: transparent;
  color: var(--dx-text-2);
  font-weight: var(--dx-weight-body);
}

@media (prefers-reduced-motion: reduce) {
  .fill {
    transition: none;
  }
}
</style>
