<script setup lang="ts" generic="T extends string">
import { ChevronDown } from '@lucide/vue'
import { useId } from 'vue'

import DxIcon from './DxIcon.vue'

/**
 * A labelled choice on the platform's own select, so it opens the native picker on a phone
 * and keeps every keyboard behaviour; only its closed face is styled.
 */
defineProps<{
  modelValue: T
  options: readonly { value: T; label: string }[]
  label: string
  inline?: boolean
}>()
defineOptions({ inheritAttrs: false })
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
const id = useId()
</script>

<template>
  <div class="select-field" :class="{ inline }">
    <label :for="id" class="label">{{ label }}</label>
    <span class="control">
      <select
        :id="id"
        class="select"
        :value="modelValue"
        v-bind="$attrs"
        @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value as T)"
      >
        <option v-for="option in options" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <DxIcon :icon="ChevronDown" :size="16" class="chevron" />
    </span>
  </div>
</template>

<style scoped>
.select-field {
  display: grid;
  gap: var(--dx-space-1);
  min-width: 0;
}

.select-field.inline {
  display: inline-flex;
  align-items: center;
  gap: var(--dx-space-2);
}

.label {
  font-size: var(--dx-text-dense);
  font-weight: var(--dx-weight-label);
}

.inline .label {
  color: var(--dx-text-2);
}

.control {
  position: relative;
  display: inline-flex;
  min-width: 0;
}

.select {
  min-width: 12rem;
  max-width: 100%;
  min-height: var(--dx-target);
  padding: 0 calc(var(--dx-space-3) + 20px) 0 var(--dx-space-3);
  border: var(--dx-line) solid var(--dx-border-strong);
  border-radius: var(--dx-radius-control);
  background: var(--dx-surface);
  color: var(--dx-text);
  font-size: var(--dx-text-dense);
  appearance: none;
  cursor: pointer;
}

.chevron {
  position: absolute;
  top: 50%;
  right: var(--dx-space-3);
  color: var(--dx-text-2);
  pointer-events: none;
  transform: translateY(-50%);
}

@media (max-width: 720px) {
  .select-field.inline {
    display: grid;
  }

  .select {
    width: 100%;
    min-width: 0;
  }

  .control {
    display: flex;
  }
}
</style>
