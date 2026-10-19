<script setup lang="ts">
import { computed } from 'vue'

import { level as formatLevel } from '@/lib/format'

/**
 * The conformal prediction set as chips: the plates that cannot be ruled out at the stated
 * level. The read itself is the chip with the accent outline. An empty set and a missing one
 * are states with their own words, not errors.
 */
const props = defineProps<{
  set: string[] | null
  level: number | null
  prediction: string | null
}>()

const levelText = computed(() => formatLevel(props.level))
const state = computed(() => {
  if (props.set === null) return 'none'
  if (props.set.length === 0) return 'empty'
  return props.set.length === 1 ? 'single' : 'several'
})
</script>

<template>
  <section class="set" :data-state="state" data-testid="conformal-set" aria-label="Prediction set">
    <h3 class="title">
      Plates that cannot be ruled out
      <span v-if="level !== null" class="level">at {{ levelText }}</span>
    </h3>
    <p v-if="state === 'none'" class="explain dx-footnote">
      No set: this read is not calibrated, so no plate can be certified.
    </p>
    <template v-else-if="state === 'empty'">
      <p class="empty">Empty set</p>
      <p class="explain dx-footnote">
        No plate is certain enough to certify at {{ levelText }}. That is a signal, not an error:
        the read goes to review.
      </p>
    </template>
    <template v-else>
      <ul class="chips">
        <li
          v-for="plate in set ?? []"
          :key="plate"
          class="chip"
          :class="{ read: plate === prediction }"
        >
          <span class="dx-plate">{{ plate }}</span>
          <span v-if="plate === prediction" class="dx-sr-only">(the read)</span>
        </li>
      </ul>
      <p v-if="state === 'single'" class="explain dx-footnote">
        One plate is certified at {{ levelText }}.
      </p>
      <p v-else class="explain dx-footnote">
        {{ set?.length }} plates remain possible at {{ levelText }}; on synthetic calibration data
        the set holds the true plate with that probability, so the read goes to review.
      </p>
    </template>
  </section>
</template>

<style scoped>
.set {
  display: grid;
  gap: var(--dx-space-2);
}

.title {
  font-size: var(--dx-text-dense);
  font-weight: var(--dx-weight-label);
}

.level {
  color: var(--dx-text-2);
  font-weight: var(--dx-weight-body);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--dx-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.chip {
  padding: var(--dx-space-1) var(--dx-space-3);
  border: var(--dx-line) solid var(--dx-border-strong);
  border-radius: var(--dx-radius-control);
  background: var(--dx-surface);
  font-size: var(--dx-text-headline);
}

.chip.read {
  border-color: var(--dx-accent);
  background: var(--dx-accent-soft);
  box-shadow: inset 0 0 0 1px var(--dx-accent);
}

.empty {
  justify-self: start;
  padding: var(--dx-space-1) var(--dx-space-3);
  border: var(--dx-line) dashed var(--dx-warning);
  border-radius: var(--dx-radius-control);
  color: var(--dx-warning);
  font-weight: var(--dx-weight-label);
}

.explain {
  color: var(--dx-text-2);
}
</style>
