<script setup lang="ts">
import { computed, useId } from 'vue'

import type { PositionOut } from '@/api/types'
import { cssVar, readableOn, sequential } from '@/lib/colors'
import { floorPercent, probability } from '@/lib/format'
import { heatmap } from '@/lib/fusion'
import { LETTERS, symbolLabel } from '@/lib/plate'
import { useThemeStore } from '@/stores/theme'

const props = withDefaults(defineProps<{ positions: PositionOut[]; minimum?: number }>(), {
  minimum: 0.005,
})

const theme = useThemeStore()
const id = useId()

const CELL_W = 40
const CELL_H = 28
const SEP_W = 14
const LABEL_W = 44
const HEAD_H = 50

const data = computed(() => heatmap(props.positions, props.minimum))

// Separator columns become thin spacers: their symbol is fixed by the grammar.
const layout = computed(() => {
  let x = LABEL_W
  return data.value.columns.map((column) => {
    const width = column.separator ? SEP_W : CELL_W
    const entry = { ...column, x, width }
    x += width
    return entry
  })
})
const width = computed(() => {
  const last = layout.value[layout.value.length - 1]
  return last ? last.x + last.width + 4 : LABEL_W + 4
})
const height = computed(() => HEAD_H + data.value.symbols.length * CELL_H + 4)
const rowOf = computed(() => new Map(data.value.symbols.map((s, i) => [s, i])))

const palette = computed(() => {
  void theme.resolved // re-read the tokens when the theme changes
  return sequential(cssVar('--dx-heat-low', '#f1f5f9'), cssVar('--dx-heat-high', '#0f766e'))
})

const cells = computed(() => {
  const columns = new Map(layout.value.map((c) => [c.position, c]))
  return data.value.cells
    .filter((cell) => !columns.get(cell.position)?.separator)
    .map((cell) => {
      const column = columns.get(cell.position)
      const fill = palette.value(cell.probability)
      return {
        ...cell,
        x: column?.x ?? 0,
        y: HEAD_H + (rowOf.value.get(cell.symbol) ?? 0) * CELL_H,
        fill,
        ink: readableOn(fill),
        text: cell.probability >= 0.01 ? floorPercent(cell.probability) : '',
      }
    })
})

const summary = computed(() =>
  data.value.columns
    .filter((c) => !c.separator)
    .map((c) => `${symbolLabel(c.symbol)} ${probability(c.confidence, 1)}`)
    .join(', '),
)

function isArabic(symbol: string) {
  return (LETTERS as readonly string[]).includes(symbol)
}

function runnerUp(position: PositionOut): string {
  const second = position.distribution.find((d) => d.symbol !== position.symbol)
  return second ? `${symbolLabel(second.symbol)} ${probability(second.probability, 1)}` : '–'
}
</script>

<template>
  <figure class="heatmap" data-testid="character-heatmap">
    <div class="dx-scroll-x" role="region" :aria-label="'Character heatmap'" tabindex="0">
      <svg
        :viewBox="`0 0 ${width} ${height}`"
        :width="width"
        :height="height"
        role="img"
        :aria-labelledby="`${id}-title ${id}-desc`"
      >
        <title :id="`${id}-title`">Per-character confidence of the fused read</title>
        <desc :id="`${id}-desc`">{{ summary }}</desc>
        <g class="heads">
          <g v-for="column in layout" :key="column.position">
            <template v-if="!column.separator">
              <text
                class="head-symbol"
                :x="column.x + CELL_W / 2"
                y="22"
                text-anchor="middle"
                :lang="isArabic(column.symbol) ? 'ar' : undefined"
              >
                {{ column.symbol }}
              </text>
              <text class="head-conf" :x="column.x + CELL_W / 2" y="40" text-anchor="middle">
                {{ floorPercent(column.confidence) }}
              </text>
            </template>
            <text
              v-else
              class="head-sep"
              :x="column.x + SEP_W / 2"
              y="22"
              text-anchor="middle"
              aria-hidden="true"
            >
              -
            </text>
          </g>
        </g>
        <g class="labels">
          <text
            v-for="(symbol, row) in data.symbols"
            :key="symbol"
            class="row-label"
            :x="LABEL_W - 10"
            :y="HEAD_H + row * CELL_H + CELL_H / 2 + 4"
            text-anchor="end"
          >
            {{ symbol === '-' ? 'sep' : symbol }}
          </text>
        </g>
        <g class="cells">
          <g v-for="cell in cells" :key="`${cell.position}-${cell.symbol}`">
            <rect
              :x="cell.x + 1"
              :y="cell.y + 1"
              :width="CELL_W - 2"
              :height="CELL_H - 2"
              rx="4"
              :fill="cell.fill"
              :class="{ winner: cell.winner }"
            >
              <title>
                Position {{ cell.position + 1 }}, {{ symbolLabel(cell.symbol) }}:
                {{ probability(cell.probability, 2) }}
              </title>
            </rect>
            <text
              v-if="cell.text"
              class="cell-text"
              :x="cell.x + CELL_W / 2"
              :y="cell.y + CELL_H / 2 + 4"
              text-anchor="middle"
              :fill="cell.ink"
            >
              {{ cell.text }}
            </text>
          </g>
        </g>
      </svg>
    </div>
    <div class="legend" aria-hidden="true">
      <span class="ramp" />
      <span class="tick" style="left: 0">0</span>
      <span class="tick" style="left: 10%">1%</span>
      <span class="tick" style="left: 50%">25%</span>
      <span class="tick end" style="left: 100%">100%</span>
    </div>
    <figcaption class="dx-small dx-muted">
      Columns are the characters of the fused plate with their confidence, rows the symbols the
      views' hypotheses put there, in whole per cent rounded down; the outlined cell is the read.
      Probabilities are weighted over all views after aligning each hypothesis to the read.
    </figcaption>
    <table class="dx-sr-only">
      <caption>
        Character confidence
      </caption>
      <thead>
        <tr>
          <th scope="col">Position</th>
          <th scope="col">Read</th>
          <th scope="col">Confidence</th>
          <th scope="col">Runner-up</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="position in positions" :key="position.index">
          <td>{{ position.index + 1 }}</td>
          <td>{{ symbolLabel(position.symbol) }}</td>
          <td>{{ probability(position.confidence, 1) }}</td>
          <td>{{ runnerUp(position) }}</td>
        </tr>
      </tbody>
    </table>
  </figure>
</template>

<style scoped>
.heatmap {
  margin: 0;
  display: grid;
  gap: var(--dx-space-2);
  min-width: 0;
}

svg {
  display: block;
  max-width: none;
  font-family: var(--dx-font-sans);
}

.head-symbol {
  font-family: var(--dx-font-plate);
  font-size: 20px;
  font-weight: 700;
  fill: var(--dx-text);
}

.head-conf {
  font-size: 11px;
  fill: var(--dx-text-muted);
  font-variant-numeric: tabular-nums;
}

.head-sep {
  font-size: 16px;
  fill: var(--dx-text-muted);
}

.row-label {
  font-family: var(--dx-font-plate);
  font-size: 15px;
  font-weight: 700;
  fill: var(--dx-text-muted);
}

.cells rect.winner {
  stroke: var(--dx-text);
  stroke-width: 2;
}

.legend {
  position: relative;
  width: min(240px, 100%);
  height: 30px;
  margin-left: 44px;
  font-size: var(--dx-text-xs);
  color: var(--dx-text-muted);
}

.ramp {
  position: absolute;
  inset: 0 0 auto;
  height: 8px;
  border-radius: 4px;
  border: 1px solid var(--dx-border);
  background: linear-gradient(to right, var(--dx-heat-low), var(--dx-heat-high));
}

.tick {
  position: absolute;
  top: 12px;
  transform: translateX(-50%);
  font-variant-numeric: tabular-nums;
}

.tick:first-of-type {
  transform: none;
}

.tick.end {
  transform: translateX(-100%);
}

.cell-text {
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}
</style>
