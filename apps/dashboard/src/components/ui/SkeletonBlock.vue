<script setup lang="ts">
/**
 * Placeholder shapes for content on its way: lines of text, a table, a figure or a plate,
 * each the size of what will replace it, so nothing jumps when it arrives.
 */
withDefaults(
  defineProps<{
    kind?: 'lines' | 'table' | 'figure' | 'plate'
    lines?: number
    rows?: number
    label?: string
  }>(),
  { kind: 'lines', lines: 3, rows: 4, label: 'Loading' },
)
</script>

<template>
  <div class="skeleton" :class="kind" role="status" :aria-label="label" data-testid="loading">
    <template v-if="kind === 'lines'">
      <span
        v-for="n in lines"
        :key="n"
        class="dx-skeleton line"
        :style="{ width: n === lines ? '60%' : '100%' }"
      />
    </template>
    <template v-else-if="kind === 'table'">
      <span class="dx-skeleton head" />
      <span v-for="n in rows" :key="n" class="dx-skeleton row" />
    </template>
    <span v-else-if="kind === 'figure'" class="dx-skeleton figure-box" />
    <template v-else>
      <span class="dx-skeleton plate-box" />
      <span class="dx-skeleton line" style="width: 70%" />
      <span class="dx-skeleton line" style="width: 45%" />
    </template>
  </div>
</template>

<style scoped>
.skeleton {
  display: grid;
  gap: var(--dx-space-2);
  min-width: 0;
}

.line {
  height: 0.75rem;
}

.head {
  height: 0.625rem;
  width: 40%;
}

.row {
  height: 1.75rem;
}

.figure-box {
  height: 14rem;
}

.plate-box {
  width: min(100%, 18rem);
  height: 4.5rem;
  margin-bottom: var(--dx-space-2);
  border-radius: var(--dx-radius-panel);
}
</style>
