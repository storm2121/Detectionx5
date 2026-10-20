<script setup lang="ts">
import { computed } from 'vue'

import type { DetectorEvalResult } from '@/api/results'
import { fixed, integer } from '@/lib/format'

/**
 * The detector on the labelled street photos beside the synthetic street scenes: precision,
 * recall and mAP from one Ultralytics validation pass each, so no interval. The synthetic
 * column says it is synthetic, and the caption says what the real column cannot claim.
 */
const props = defineProps<{
  real: DetectorEvalResult
  synthetic?: DetectorEvalResult | null
  /** Why the real column is not independent of the detector's training, in words. */
  overlap?: string
}>()

const ROWS = [
  ['precision', 'Precision'],
  ['recall', 'Recall'],
  ['map50', 'mAP@50'],
  ['map50_95', 'mAP@50-95'],
] as const

const realHead = computed(
  () =>
    `Street photos (n = ${integer(props.real.counts?.images)} photos, ${integer(props.real.counts?.plates)} plates)`,
)
const syntheticHead = computed(() =>
  props.synthetic
    ? `Synthetic street scenes (n = ${integer(props.synthetic.counts?.images)} scenes)`
    : '',
)
</script>

<template>
  <div
    class="dx-scroll-x"
    role="region"
    aria-label="The detector on real photos and on synthetic scenes"
    tabindex="0"
    data-testid="detector-comparison"
  >
    <table class="dx-table">
      <caption>
        {{
          `The detector, ${real.weights}, one Ultralytics validation pass per set at image size ${real.imgsz}, so no interval.`
        }}
        <template v-if="overlap">
          {{ ` The street photos are not an independent measurement: ${overlap}.` }}
        </template>
        <template v-if="synthetic"> Synthetic results are not real-world accuracy. </template>
      </caption>
      <thead>
        <tr>
          <th scope="col">Metric</th>
          <th scope="col">{{ realHead }}</th>
          <th v-if="synthetic" scope="col">{{ syntheticHead }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="[key, label] in ROWS" :key="key">
          <th scope="row">{{ label }}</th>
          <td class="dx-num">{{ fixed(real.metrics[key], 3) }}</td>
          <td v-if="synthetic" class="dx-num">{{ fixed(synthetic.metrics[key], 3) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
