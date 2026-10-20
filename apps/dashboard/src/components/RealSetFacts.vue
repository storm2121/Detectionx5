<script setup lang="ts">
import { computed } from 'vue'

import type { EvalResult } from '@/api/results'
import { integer } from '@/lib/format'

import NoticeBlock from './ui/NoticeBlock.vue'

/**
 * What the labelled real set is, in its own counts and words (`set.card`, written beside
 * the labels and copied into the results; ADR 0013): how many photos and plates, what the
 * photos are copies of, how the text was transcribed and what was left out, what the
 * intervals resample, and what the detector has already seen. Nothing here is typed by hand.
 */
const props = defineProps<{ real: EvalResult }>()

const info = computed(() => props.real.set)
const card = computed(() => info.value.card ?? {})

function list(parts: string[]): string {
  if (parts.length <= 1) return parts.join('')
  return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`
}

const description = computed(() => {
  const what = info.value.note ?? card.value.description ?? 'labelled real photos'
  const head = card.value.photos
    ? `${what}: ${integer(card.value.photos)} photos holding ${integer(card.value.boxes)} labelled plates`
    : what
  const copies = Object.entries(card.value.copies ?? {}).map(
    ([kind, count]) => `${integer(count)} ${kind}`,
  )
  const source = card.value.camera_photos
    ? `, every one an augmented copy of one of ${integer(card.value.camera_photos)} camera photos (${list(copies)})`
    : ''
  const restored = card.value.restored ? `; ${card.value.restored}` : ''
  return `${head.charAt(0).toUpperCase()}${head.slice(1)}${source}${restored}.`
})

const transcription = computed(() => {
  const t = card.value.transcription
  if (!t) return ''
  const excluded = Object.entries(card.value.excluded ?? {})
  const left = excluded.reduce((sum, [, count]) => sum + count, 0)
  const reasons = list(excluded.map(([why, count]) => `${integer(count)} ${why}`))
  return (
    `Plate text transcribed by eye in two passes over differently ordered contact sheets, ` +
    `checked against the plate grammar: the passes agreed on ${integer(t.agreed)} of ` +
    `${integer(t.crops)} crops (all ${integer(t.identical_when_both_readable)} where both were ` +
    `readable), and a zoomed third pass accepted ${integer(t.accepted_in_third_pass)} of the ` +
    `${integer(t.third_pass)} it saw. ${integer(card.value.text_labels ?? info.value.n)} plates in ` +
    `${integer(card.value.labelled_photos ?? info.value.photos)} photos are labelled ` +
    `(${integer(card.value.vehicles)} distinct vehicles)` +
    (left ? `; ${integer(left)} were left out: ${reasons}.` : '.')
  )
})

const resampling = computed(() => {
  const boot = props.real.bootstrap
  return boot.unit === 'group'
    ? `95% intervals resample the ${integer(boot.groups)} vehicle groups (a vehicle with every photo it appears in), not single photos, since copies of one photo and repeat photos of one vehicle are not independent.`
    : `95% intervals resample single ${boot.unit}s.`
})
</script>

<template>
  <div class="facts" data-testid="real-set-facts">
    <p class="dx-measure dx-secondary">{{ description }}</p>
    <NoticeBlock v-if="card.detector_overlap" tone="note" data-testid="detector-overlap">
      <span>
        <strong>The detector has seen these scenes.</strong>
        {{
          ` ${card.detector_overlap.charAt(0).toUpperCase()}${card.detector_overlap.slice(1)}: the end-to-end and detector figures are not independent of its training data. The recogniser has only ever seen synthetic plates.`
        }}
      </span>
    </NoticeBlock>
    <p v-if="transcription" class="dx-footnote dx-secondary dx-measure">{{ transcription }}</p>
    <p class="dx-footnote dx-secondary dx-measure">{{ resampling }}</p>
  </div>
</template>

<style scoped>
.facts {
  display: grid;
  gap: var(--dx-space-3);
}

.facts p {
  margin: 0;
}
</style>
