<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), { label: 'Loading' })
</script>

<template>
  <div class="loading" role="status" data-testid="loading">
    <span class="spinner" aria-hidden="true" />
    <span>{{ label }}…</span>
  </div>
</template>

<style scoped>
.loading {
  display: inline-flex;
  align-items: center;
  gap: var(--dx-space-2);
  color: var(--dx-text-muted);
  font-size: var(--dx-text-sm);
}

.spinner {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--dx-border-strong);
  border-top-color: var(--dx-accent);
  animation: spin 800ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
