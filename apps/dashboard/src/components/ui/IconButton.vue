<script setup lang="ts">
import { type Component, useId } from 'vue'

import { vPress } from '@/motion/press'

import DxIcon from './DxIcon.vue'

/**
 * An icon-only button, for dense toolbars only (the top bar). Its label is its accessible
 * name and its tooltip, which appears on hover and on keyboard focus and grows from the
 * button it describes.
 */
defineProps<{ icon: Component; label: string; pressed?: boolean | null }>()
defineOptions({ inheritAttrs: false })
defineEmits<{ click: [event: MouseEvent] }>()
const tip = useId()
</script>

<template>
  <span class="wrap">
    <button
      v-press
      class="icon-button"
      type="button"
      :aria-label="label"
      :aria-describedby="tip"
      :aria-pressed="pressed ?? undefined"
      v-bind="$attrs"
      @click="$emit('click', $event)"
    >
      <DxIcon :icon="icon" :size="20" />
    </button>
    <span :id="tip" class="tip" role="tooltip">{{ label }}</span>
  </span>
</template>

<style scoped>
.wrap {
  position: relative;
  display: inline-flex;
}

.icon-button {
  display: grid;
  place-items: center;
  width: var(--dx-target);
  height: var(--dx-target);
  padding: 0;
  border: 0;
  border-radius: var(--dx-radius-control);
  background: transparent;
  color: var(--dx-text-2);
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.icon-button:hover {
  background: color-mix(in srgb, var(--dx-text) 7%, transparent);
  color: var(--dx-text);
}

/* a floating surface: the one place a shadow belongs; it scales from its trigger */
.tip {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 30;
  padding: var(--dx-space-1) var(--dx-space-2);
  border-radius: var(--dx-radius-control);
  background: var(--dx-gray-9);
  color: var(--dx-gray-1);
  box-shadow: var(--dx-shadow-float);
  font-family: var(--dx-font-small);
  font-size: var(--dx-text-caption);
  letter-spacing: var(--dx-track-caption);
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transform: scale(0.96);
  transform-origin: top right;
  transition:
    opacity 120ms var(--dx-ease-out),
    transform 120ms var(--dx-ease-out);
}

.wrap:hover .tip,
.icon-button:focus-visible + .tip {
  opacity: 1;
  transform: none;
  transition-delay: 300ms;
}

.icon-button:focus-visible + .tip {
  transition-delay: 0ms;
}

@media (prefers-reduced-motion: reduce) {
  .tip {
    transform: none;
  }
}
</style>
