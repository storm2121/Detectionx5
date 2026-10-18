<script setup lang="ts">
defineProps<{ message: string; title?: string }>()
</script>

<template>
  <div class="error" role="alert" data-testid="error-note">
    <strong>{{ title ?? 'Something went wrong' }}</strong>
    <span>{{ message }}</span>
    <slot />
  </div>
</template>

<style scoped>
.error {
  display: grid;
  gap: 2px;
  padding: var(--dx-space-3) var(--dx-space-4);
  border-radius: var(--dx-radius-m);
  border: 1px solid color-mix(in srgb, var(--dx-bad) 35%, transparent);
  background: var(--dx-bad-soft);
  color: var(--dx-text);
  font-size: var(--dx-text-sm);
}

strong {
  color: var(--dx-bad);
}
</style>
