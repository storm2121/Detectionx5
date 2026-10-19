<script setup lang="ts" generic="T extends string">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { springTo } from '@/motion/springs'

/**
 * A segmented control (a radio group). Segments share the width equally, so the selection
 * thumb only translates: it springs from wherever it is to the chosen segment, and a second
 * choice mid-flight redirects it. Arrow keys move the choice, as in any radio group.
 */
const props = withDefaults(
  defineProps<{
    modelValue: T
    options: readonly { value: T; label: string }[]
    label: string
    size?: 'regular' | 'small'
  }>(),
  { size: 'regular' },
)
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()

const thumb = ref<HTMLElement | null>(null)
const buttons = ref<HTMLButtonElement[]>([])
const index = computed(() =>
  Math.max(
    0,
    props.options.findIndex((o) => o.value === props.modelValue),
  ),
)

function place(animate: boolean) {
  const element = thumb.value
  if (!element) return
  const x = `${index.value * 100}%`
  if (animate) springTo(element, { x })
  else element.style.transform = `translateX(${x})`
}

function choose(value: T) {
  if (value !== props.modelValue) emit('update:modelValue', value)
}

function onKey(event: KeyboardEvent, position: number) {
  const last = props.options.length - 1
  const step: Record<string, number> = {
    ArrowRight: 1,
    ArrowDown: 1,
    ArrowLeft: -1,
    ArrowUp: -1,
    Home: -position,
    End: last - position,
  }
  const delta = step[event.key]
  if (delta === undefined) return
  event.preventDefault()
  const next = Math.min(last, Math.max(0, position + delta))
  const option = props.options[next]
  if (!option) return
  choose(option.value)
  void nextTick(() => buttons.value[next]?.focus())
}

onMounted(() => place(false))
watch(index, () => place(true))
</script>

<template>
  <div
    class="segmented"
    :class="size"
    role="radiogroup"
    :aria-label="label"
    :style="{ '--segments': options.length }"
  >
    <span ref="thumb" class="thumb" aria-hidden="true" />
    <button
      v-for="(option, position) in options"
      :key="option.value"
      ref="buttons"
      type="button"
      role="radio"
      class="segment"
      :aria-checked="option.value === modelValue"
      :tabindex="option.value === modelValue ? 0 : -1"
      @click="choose(option.value)"
      @keydown="onKey($event, position)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
.segmented {
  position: relative;
  display: inline-grid;
  justify-self: start;
  width: max-content;
  grid-template-columns: repeat(var(--segments), minmax(0, 1fr));
  max-width: 100%;
  padding: 2px;
  border-radius: calc(var(--dx-radius-control) + 2px);
  background: var(--dx-surface-inset);
  box-shadow: inset 0 0 0 var(--dx-line) var(--dx-border);
}

.thumb {
  position: absolute;
  top: 2px;
  bottom: 2px;
  left: 2px;
  width: calc((100% - 4px) / var(--segments));
  border-radius: var(--dx-radius-control);
  background: var(--dx-surface);
  box-shadow:
    var(--dx-shadow-control),
    inset 0 0 0 var(--dx-line) var(--dx-border);
}

.segment {
  position: relative;
  min-height: calc(var(--dx-target) - 4px);
  padding: 0 var(--dx-space-4);
  border: 0;
  border-radius: var(--dx-radius-control);
  background: transparent;
  color: var(--dx-text-2);
  font-size: var(--dx-text-dense);
  font-weight: var(--dx-weight-label);
  white-space: nowrap;
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.segment[aria-checked='true'] {
  color: var(--dx-text);
}

.segment:focus-visible {
  outline-offset: 0;
}

.small .segment {
  min-height: 1.75rem;
  padding: 0 var(--dx-space-3);
  font-size: var(--dx-text-footnote);
}

@media (prefers-contrast: more) {
  .thumb {
    box-shadow: inset 0 0 0 1px var(--dx-text-2);
  }
}

@media (max-width: 720px) {
  /* at phone width the control takes the row and long labels wrap inside their segment */
  .segmented {
    width: 100%;
  }

  .segment,
  .small .segment {
    min-height: calc(var(--dx-target) - 4px);
    padding: var(--dx-space-1) var(--dx-space-2);
    line-height: 1.2;
    white-space: normal;
  }
}
</style>
