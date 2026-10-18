<script setup lang="ts">
import { computed } from 'vue'

import type { Fields } from '@/api/types'

const props = withDefaults(
  defineProps<{
    fields: Fields | null
    format: string | null
    plate: string | null
    size?: 'md' | 'lg'
  }>(),
  { size: 'lg' },
)

const temporary = computed(() => props.format === 'temporary')
const label = computed(() => {
  if (!props.fields) return 'No plate read'
  if (temporary.value) return `Temporary plate: digits ${props.fields.digits}, mark WW`
  return `Standard plate: digits ${props.fields.digits}, letter ${props.fields.letter ?? ''}, region ${props.fields.region ?? ''}`
})
</script>

<template>
  <figure class="plate-wrap" :class="size" data-testid="plate-fields">
    <div v-if="fields" class="plate" :class="{ temporary }" role="img" :aria-label="label">
      <span class="face" aria-hidden="true" />
      <span class="dx-plate-text value c1" data-field="digits">{{ fields.digits }}</span>
      <span class="rule c2" aria-hidden="true" />
      <template v-if="temporary">
        <span class="dx-plate-text value c3" data-field="mark">WW</span>
        <span class="caption c1" aria-hidden="true">Digits</span>
        <span class="caption c3" aria-hidden="true">Temporary</span>
      </template>
      <template v-else>
        <span class="dx-plate-text value letter c3" lang="ar" data-field="letter">{{
          fields.letter
        }}</span>
        <span class="rule c4" aria-hidden="true" />
        <span class="dx-plate-text value c5" data-field="region">{{ fields.region }}</span>
        <span class="caption c1" aria-hidden="true">Digits</span>
        <span class="caption c3" aria-hidden="true">Letter</span>
        <span class="caption c5" aria-hidden="true">Region</span>
      </template>
    </div>
    <div v-else class="empty" role="img" aria-label="No plate read">No plate read</div>
  </figure>
</template>

<style scoped>
.plate-wrap {
  margin: 0;
  max-width: 100%;
}

.plate {
  display: inline-grid;
  grid-template-columns: auto 3px auto 3px auto;
  grid-template-rows: auto auto;
  row-gap: var(--dx-space-1);
  max-width: 100%;
}

.plate.temporary {
  grid-template-columns: auto 3px auto;
}

.face {
  grid-row: 1;
  grid-column: 1 / -1;
  background: var(--dx-plate-bg);
  border: 3px solid var(--dx-plate-rule);
  border-radius: 8px;
  box-shadow:
    inset 0 0 0 2px var(--dx-plate-bg),
    inset 0 0 0 3px color-mix(in srgb, var(--dx-plate-rule) 35%, transparent),
    var(--dx-shadow-1);
}

.value {
  grid-row: 1;
  align-self: center;
  justify-self: center;
  padding: 2px var(--dx-space-4);
  color: var(--dx-plate-ink);
  font-size: var(--dx-text-plate);
  line-height: 1.3;
}

.value.letter {
  font-size: calc(var(--dx-text-plate) * 0.86);
}

.rule {
  grid-row: 1;
  width: 3px;
  margin: 9px 0;
  border-radius: 2px;
  background: var(--dx-plate-rule);
}

.caption {
  grid-row: 2;
  justify-self: center;
  font-size: var(--dx-text-xs);
  color: var(--dx-text-muted);
}

.c1 {
  grid-column: 1;
}

.c2 {
  grid-column: 2;
}

.c3 {
  grid-column: 3;
}

.c4 {
  grid-column: 4;
}

.c5 {
  grid-column: 5;
}

.md .value {
  font-size: 1.6rem;
  padding: 0 var(--dx-space-3);
}

.md .value.letter {
  font-size: 1.4rem;
}

.md .rule {
  margin: 6px 0;
}

.empty {
  display: inline-block;
  padding: var(--dx-space-3) var(--dx-space-5);
  border: 2px dashed var(--dx-border-strong);
  border-radius: 8px;
  color: var(--dx-text-muted);
  font-weight: 600;
}

@media (max-width: 480px) {
  .value {
    font-size: 2rem;
    padding: 2px var(--dx-space-3);
  }

  .value.letter {
    font-size: 1.7rem;
  }
}
</style>
