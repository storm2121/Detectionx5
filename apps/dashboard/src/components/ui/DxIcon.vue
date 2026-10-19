<script setup lang="ts">
import type { Component } from 'vue'

/**
 * A Lucide icon at one of the two sizes the console uses, with the console's stroke. An icon
 * is decorative next to its text label; give it `label` only when it stands alone.
 */
withDefaults(defineProps<{ icon: Component; size?: 16 | 20; label?: string }>(), {
  size: 16,
  label: '',
})
</script>

<template>
  <component
    :is="icon"
    class="dx-icon"
    :size="size"
    :stroke-width="1.75"
    :aria-hidden="label ? undefined : 'true'"
    :aria-label="label || undefined"
    :role="label ? 'img' : undefined"
    focusable="false"
  />
</template>

<style scoped>
.dx-icon {
  flex: none;
  vertical-align: -0.15em;
}
</style>
