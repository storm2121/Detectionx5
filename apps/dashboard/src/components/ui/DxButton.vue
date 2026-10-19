<script setup lang="ts">
import type { Component } from 'vue'

import { vPress } from '@/motion/press'

import DxIcon from './DxIcon.vue'

/**
 * The console's button. It presses on pointer-down and springs back on release; while
 * `busy` it says what it is doing in its own label instead of showing a spinner.
 */
const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'plain'
    size?: 'regular' | 'small'
    type?: 'button' | 'submit'
    disabled?: boolean
    busy?: boolean
    busyLabel?: string
    icon?: Component | null
  }>(),
  {
    variant: 'secondary',
    size: 'regular',
    type: 'button',
    disabled: false,
    busy: false,
    busyLabel: '',
    icon: null,
  },
)
defineEmits<{ click: [event: MouseEvent] }>()
</script>

<template>
  <button
    v-press
    class="dx-button"
    :class="[variant, size, { busy }]"
    :type="type"
    :disabled="disabled || busy"
    :aria-busy="busy ? 'true' : undefined"
    @click="$emit('click', $event)"
  >
    <DxIcon v-if="icon && !busy" :icon="icon" :size="16" />
    <span class="label">
      <template v-if="busy && props.busyLabel">{{ props.busyLabel }}</template>
      <slot v-else />
    </span>
  </button>
</template>

<style scoped>
.dx-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--dx-space-2);
  min-height: var(--dx-target);
  padding: 0 var(--dx-space-4);
  border: var(--dx-line) solid transparent;
  border-radius: var(--dx-radius-control);
  font-size: var(--dx-text-body);
  font-weight: var(--dx-weight-label);
  line-height: 1.2;
  white-space: nowrap;
  cursor: pointer;
  touch-action: manipulation;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.small {
  min-height: 1.875rem;
  padding: 0 var(--dx-space-3);
  font-size: var(--dx-text-dense);
}

.primary {
  background: var(--dx-accent-fill);
  color: var(--dx-on-accent);
}

.primary:hover:not(:disabled) {
  background: var(--dx-accent-fill-hover);
}

.secondary {
  background: var(--dx-surface);
  border-color: var(--dx-border-strong);
  color: var(--dx-text);
}

.secondary:hover:not(:disabled) {
  background: var(--dx-surface-inset);
}

.plain {
  padding-inline: var(--dx-space-2);
  background: transparent;
  color: var(--dx-accent);
}

.plain:hover:not(:disabled) {
  background: var(--dx-accent-soft);
}

.dx-button:disabled {
  cursor: default;
  opacity: 0.45;
}

.dx-button.busy:disabled {
  opacity: 0.8;
}

@media (prefers-contrast: more) {
  .secondary,
  .plain {
    border-color: var(--dx-text-2);
  }
}

@media (max-width: 720px) {
  .small {
    min-height: var(--dx-target);
  }
}
</style>
