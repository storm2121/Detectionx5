<script setup lang="ts">
import { animate, stagger } from 'motion'
import { computed, nextTick, onMounted, ref, useId, watch } from 'vue'

import type { Fields, PositionOut } from '@/api/types'
import { inkFor, tokenOn } from '@/lib/colors'
import { floorPercent, probability } from '@/lib/format'
import { symbolLabel } from '@/lib/plate'
import { rampOpacity, readoutColumns, readoutGroups, readoutTemplate } from '@/lib/readout'
import { reducedMotion, SPRING } from '@/motion/springs'
import { useThemeStore } from '@/stores/theme'

/**
 * The read plate, large, in both of its scripts (Latin digits, the Arabic letter in Naskh at
 * the Latin x-height), and directly under it the character heatmap on the same column grid:
 * each character's confidence sits under that character, with the other symbols the views
 * proposed there below it. Confidence is one hue, from the surface to the accent.
 */
const props = withDefaults(
  defineProps<{
    positions: PositionOut[]
    fields: Fields | null
    format: string | null
    plate: string | null
    minimum?: number
  }>(),
  { minimum: 0.01 },
)

const id = useId()
const theme = useThemeStore()
const root = ref<HTMLElement | null>(null)
const heat = ref<HTMLElement | null>(null)
const ramp = ref({ low: '#f0f0f3', high: '#0066cc' })

const columns = computed(() => readoutColumns(props.positions, props.minimum))
const groups = computed(() => readoutGroups(columns.value))
const template = computed(() => readoutTemplate(columns.value))
const characters = computed(() => columns.value.filter((c) => !c.separator).length)
const separators = computed(() => columns.value.length - characters.value)
const altRows = computed(() => Math.max(0, ...columns.value.map((c) => c.alternatives.length)))
const temporary = computed(() => props.format === 'temporary')

const label = computed(() => {
  if (!props.fields) return 'No plate read'
  if (temporary.value) return `Temporary plate: digits ${props.fields.digits}, mark WW`
  return `Standard plate: digits ${props.fields.digits}, letter ${props.fields.letter ?? ''}, region ${props.fields.region ?? ''}`
})

/** Columns grouped into the plate's fields, so each field's glyphs carry `data-field`. */
const fieldRuns = computed(() =>
  groups.value.map((group) => ({
    field:
      group.name === 'Digits'
        ? 'digits'
        : group.name === 'Letter'
          ? 'letter'
          : group.name === 'Region'
            ? 'region'
            : 'mark',
    columns: columns.value.slice(group.start, group.end + 1),
    start: group.start,
  })),
)

function ink(p: number) {
  return inkFor(ramp.value.low, ramp.value.high, rampOpacity(p)) === 'light'
    ? 'var(--dx-ink-light)'
    : 'var(--dx-ink-dark)'
}

function readTokens() {
  ramp.value = {
    low: tokenOn(root.value, '--dx-ramp-low', ramp.value.low),
    high: tokenOn(root.value, '--dx-ramp-high', ramp.value.high),
  }
}

function runnerUp(position: PositionOut): string {
  const second = [...position.distribution]
    .filter((d) => d.symbol !== position.symbol)
    .sort((a, b) => b.probability - a.probability)[0]
  return second ? `${symbolLabel(second.symbol)} ${probability(second.probability, 1)}` : 'none'
}

/** The heatmap rises into place column by column; under reduced motion it simply appears. */
async function entrance() {
  await nextTick()
  if (!heat.value || reducedMotion()) return
  const cells = heat.value.querySelectorAll('.cell')
  if (cells.length)
    animate(cells, { opacity: [0, 1], y: [4, 0] }, { ...SPRING, delay: stagger(0.02) })
}

onMounted(() => {
  readTokens()
  void entrance()
})
watch(
  () => theme.resolved,
  () => void nextTick(readTokens),
)
watch(
  () => props.positions,
  () => void entrance(),
)
</script>

<template>
  <figure
    ref="root"
    class="readout"
    :style="{ '--n': characters, '--seps': separators }"
    data-testid="plate-fields"
  >
    <template v-if="fields && columns.length">
      <div
        class="plate"
        :class="{ temporary }"
        role="img"
        :aria-label="label"
        :style="{ gridTemplateColumns: template }"
      >
        <template v-for="(run, r) in fieldRuns" :key="run.field">
          <span v-if="r > 0" class="rule" aria-hidden="true" :style="{ gridColumn: run.start }" />
          <span class="field" :data-field="run.field" aria-hidden="true"
            ><span
              v-for="column in run.columns"
              :key="column.index"
              class="glyph"
              :class="{ arabic: column.arabic }"
              :lang="column.arabic ? 'ar' : undefined"
              :style="{ gridColumn: column.index + 1 }"
              >{{ column.symbol }}</span
            ></span
          >
        </template>
      </div>
      <div class="captions" aria-hidden="true" :style="{ gridTemplateColumns: template }">
        <span
          v-for="group in groups"
          :key="group.name"
          class="caption"
          :style="{ gridColumn: `${group.start + 1} / ${group.end + 2}` }"
          >{{ group.name }}</span
        >
      </div>
      <div
        ref="heat"
        class="heat"
        aria-hidden="true"
        data-testid="character-heatmap"
        :style="{ gridTemplateColumns: template, gridTemplateRows: `repeat(${1 + altRows}, auto)` }"
      >
        <template v-for="column in columns" :key="column.index">
          <template v-if="!column.separator">
            <span
              class="cell winner"
              :style="{ gridColumn: column.index + 1, gridRow: 1, color: ink(column.confidence) }"
              :title="`${symbolLabel(column.symbol)}: ${probability(column.confidence, 2)}`"
            >
              <span class="fill" :style="{ opacity: rampOpacity(column.confidence) }" />
              <span class="value">{{ floorPercent(column.confidence) }}</span>
            </span>
            <span
              v-for="(alt, a) in column.alternatives"
              :key="alt.symbol"
              class="cell alt"
              :style="{ gridColumn: column.index + 1, gridRow: a + 2, color: ink(alt.probability) }"
              :title="`${symbolLabel(alt.symbol)}: ${probability(alt.probability, 2)}`"
            >
              <span class="fill" :style="{ opacity: rampOpacity(alt.probability) }" />
              <span class="value"
                ><span class="dx-plate alt-symbol">{{ alt.symbol }}</span>
                {{ floorPercent(alt.probability) }}</span
              >
            </span>
          </template>
        </template>
      </div>
      <figcaption class="legend">
        <span class="ramp" aria-hidden="true"><span class="ramp-fill" /></span>
        <span>
          Confidence of each character in whole per cent, rounded down; below it, the other symbols
          the views proposed there. Weighted over all views after aligning each one to the read.
        </span>
      </figcaption>
      <table class="dx-sr-only">
        <caption>
          Confidence of each character of the read
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
    </template>
    <div v-else :id="`${id}-none`" class="none" role="img" aria-label="No plate read">
      No plate read
    </div>
  </figure>
</template>

<style scoped>
.readout {
  --cell: min(3.25rem, calc((100cqi - 2 * var(--dx-space-3) - var(--seps) * 0.875rem) / var(--n)));
  --sep: 0.875rem;
  display: grid;
  gap: var(--dx-space-2);
  min-width: 0;
  container-type: inline-size;
}

.plate,
.captions,
.heat {
  display: grid;
  justify-content: start;
  padding: 0 var(--dx-space-3);
}

/* the plate itself: a white plate with its printed separator rules, in both themes */
.plate {
  grid-template-rows: auto;
  align-items: center;
  width: max-content;
  max-width: 100%;
  padding-block: var(--dx-space-1);
  /* the border sits inside the padding, so the glyphs keep the heatmap's columns */
  padding-inline: calc(var(--dx-space-3) - 1.5px);
  border: 1.5px solid var(--dx-plate-rule);
  border-radius: 8px;
  background: var(--dx-plate-bg);
  color: var(--dx-plate-ink);
}

.field {
  display: contents;
}

.glyph {
  grid-row: 1;
  justify-self: center;
  font-family: var(--dx-font-display);
  font-size: min(var(--dx-text-plate), calc(var(--cell) * 1.02));
  font-weight: var(--dx-weight-title);
  line-height: 1.25;
  letter-spacing: 0;
}

.glyph.arabic {
  font-style: normal;
}

.rule {
  grid-row: 1;
  justify-self: center;
  align-self: stretch;
  width: 2px;
  margin: 0.4em 0;
  border-radius: 1px;
  background: var(--dx-plate-rule);
}

.temporary .rule {
  background: transparent;
}

.captions {
  margin-top: calc(var(--dx-space-1) * -1);
}

.caption {
  justify-self: center;
  color: var(--dx-text-2);
  font-family: var(--dx-font-small);
  font-size: var(--dx-text-caption);
  letter-spacing: var(--dx-track-caption);
  white-space: nowrap;
}

.heat {
  row-gap: 3px;
  column-gap: 0;
}

.cell {
  position: relative;
  display: grid;
  place-items: center;
  width: calc(var(--cell) - 3px);
  height: 1.625rem;
  justify-self: center;
  overflow: hidden;
  border-radius: 4px;
  background: var(--dx-ramp-low);
  font-size: var(--dx-text-caption);
  font-weight: var(--dx-weight-label);
}

.cell.alt {
  height: 1.375rem;
  font-weight: var(--dx-weight-body);
}

.fill {
  position: absolute;
  inset: 0;
  background: var(--dx-ramp-high);
}

.value {
  position: relative;
  white-space: nowrap;
}

.cell.winner {
  box-shadow: inset 0 0 0 1.5px var(--dx-text);
}

.alt-symbol {
  font-weight: var(--dx-weight-title);
}

.legend {
  display: flex;
  align-items: flex-start;
  gap: var(--dx-space-3);
  max-width: var(--dx-measure);
  color: var(--dx-text-2);
  font-size: var(--dx-text-footnote);
  line-height: 1.4;
}

.ramp {
  position: relative;
  flex: none;
  width: 4rem;
  height: 0.5rem;
  margin-top: 0.35rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--dx-ramp-low);
}

.ramp-fill {
  position: absolute;
  inset: 0;
  background: linear-gradient(to right, transparent, var(--dx-ramp-high));
}

.none {
  display: inline-grid;
  place-items: center;
  min-height: 4.5rem;
  padding: 0 var(--dx-space-5);
  border: 1.5px dashed var(--dx-border-strong);
  border-radius: 8px;
  color: var(--dx-text-2);
  font-weight: var(--dx-weight-label);
}

@media (prefers-contrast: more) {
  .cell {
    box-shadow: inset 0 0 0 1px var(--dx-border-strong);
  }
}
</style>
