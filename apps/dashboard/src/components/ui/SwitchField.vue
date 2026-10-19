<script setup lang="ts">
import { onMounted, ref, useId, watch } from 'vue'

import { springTo } from '@/motion/springs'

/** An on/off switch with its label; the knob springs across and can be flicked back. */
const props = defineProps<{ modelValue: boolean; label: string; hint?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const id = useId()
/** The knob's travel: the track's inner width less the knob. */
const TRAVEL = '1.125rem'
const knob = ref<HTMLElement | null>(null)

function place(animate: boolean) {
  const element = knob.value
  if (!element) return
  const x = props.modelValue ? TRAVEL : '0rem'
  if (animate) springTo(element, { x })
  else element.style.transform = `translateX(${x})`
}

onMounted(() => place(false))
watch(
  () => props.modelValue,
  () => place(true),
)
</script>

<template>
  <div class="switch-field">
    <button
      :id="id"
      type="button"
      role="switch"
      class="switch"
      :aria-checked="modelValue"
      :aria-labelledby="`${id}-label`"
      :aria-describedby="hint ? `${id}-hint` : undefined"
      @click="emit('update:modelValue', !modelValue)"
    >
      <span ref="knob" class="knob" aria-hidden="true" />
    </button>
    <span class="text">
      <label :id="`${id}-label`" :for="id" class="label">{{ label }}</label>
      <span v-if="hint" :id="`${id}-hint`" class="hint dx-footnote">{{ hint }}</span>
    </span>
  </div>
</template>

<style scoped>
.switch-field {
  display: flex;
  align-items: flex-start;
  gap: var(--dx-space-3);
}

.switch {
  position: relative;
  flex: none;
  width: 2.625rem;
  height: 1.5rem;
  margin-top: 1px;
  padding: 2px;
  border: 0;
  border-radius: 999px;
  background: var(--dx-gray-4);
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.switch[aria-checked='true'] {
  background: var(--dx-accent-fill);
}

.knob {
  display: block;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: var(--dx-knob);
  box-shadow: var(--dx-shadow-control);
}

.text {
  display: grid;
  gap: 2px;
}

.label {
  font-weight: var(--dx-weight-label);
  cursor: pointer;
}

.hint {
  color: var(--dx-text-2);
}

@media (max-width: 720px) {
  .switch {
    margin-top: 0;
  }

  .switch::after {
    position: absolute;
    inset: -10px;
    content: '';
  }
}
</style>
