<script setup lang="ts">
import { computed } from 'vue'

import { level as formatLevel } from '@/lib/format'

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
  <section
    class="conformal"
    :data-state="state"
    data-testid="conformal-set"
    aria-labelledby="set-title"
  >
    <h3 id="set-title" class="title">
      Conformal set
      <span v-if="level !== null" class="level">at {{ levelText }}</span>
    </h3>
    <p v-if="state === 'none'" class="explain">
      No set: this read is not calibrated, so no plate can be certified.
    </p>
    <template v-else-if="state === 'empty'">
      <p class="empty-chip">Empty set</p>
      <p class="explain">
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
          :class="{ top: plate === prediction }"
        >
          <span class="dx-plate-text">{{ plate }}</span>
        </li>
      </ul>
      <p v-if="state === 'single'" class="explain">One plate is certified at {{ levelText }}.</p>
      <p v-else class="explain">
        {{ set?.length }} plates remain possible at {{ levelText }}; the set holds the true plate
        with that probability on synthetic calibration data, so the read goes to review.
      </p>
    </template>
  </section>
</template>

<style scoped>
.conformal {
  display: grid;
  gap: var(--dx-space-2);
}

.title {
  font-size: var(--dx-text-md);
  font-weight: 600;
}

.level {
  color: var(--dx-text-muted);
  font-weight: 500;
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
  padding: 4px 12px;
  border-radius: var(--dx-radius-s);
  border: 1px solid var(--dx-border-strong);
  background: var(--dx-surface-sunken);
  font-size: var(--dx-text-lg);
}

.chip.top {
  border-color: var(--dx-accent);
  background: var(--dx-accent-soft);
}

.empty-chip {
  justify-self: start;
  padding: 4px 12px;
  border-radius: var(--dx-radius-s);
  border: 1px dashed var(--dx-warn);
  color: var(--dx-warn);
  background: var(--dx-warn-soft);
  font-weight: 600;
}

.explain {
  color: var(--dx-text-muted);
  font-size: var(--dx-text-sm);
}
</style>
