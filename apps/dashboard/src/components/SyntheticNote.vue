<script setup lang="ts">
withDefaults(defineProps<{ detail?: string }>(), { detail: '' })
</script>

<template>
  <p class="synthetic" role="note" data-testid="synthetic-note">
    <svg class="icon" viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="8.25" fill="none" stroke="currentColor" stroke-width="1.5" />
      <path d="M10 9v5M10 6.2v.1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </svg>
    <span>
      <strong>Synthetic results are not real-world accuracy.</strong>
      <template v-if="detail">{{ ' ' + detail }}</template>
      <slot />
    </span>
  </p>
</template>

<style scoped>
.synthetic {
  display: flex;
  gap: var(--dx-space-2);
  align-items: flex-start;
  padding: var(--dx-space-3) var(--dx-space-4);
  border: 1px solid color-mix(in srgb, var(--dx-info) 30%, transparent);
  border-radius: var(--dx-radius-m);
  background: var(--dx-info-soft);
  color: var(--dx-text);
  font-size: var(--dx-text-sm);
}

.icon {
  flex: none;
  width: 18px;
  height: 18px;
  margin-top: 1px;
  color: var(--dx-info);
}
</style>
