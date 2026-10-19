<script setup lang="ts">
import { useId } from 'vue'

/**
 * A labelled text input. Validation is inline: `error` is shown under the field as the
 * person types or leaves it, never only after a submit, and it says what to do.
 */
withDefaults(
  defineProps<{
    modelValue: string
    label: string
    hint?: string
    error?: string | null
    placeholder?: string
    plate?: boolean
    id?: string
    autocomplete?: string
  }>(),
  { hint: '', error: null, placeholder: '', plate: false, id: '', autocomplete: 'off' },
)
defineOptions({ inheritAttrs: false })
const emit = defineEmits<{ 'update:modelValue': [value: string]; blur: [] }>()
const fallback = useId()
</script>

<template>
  <div class="field" :class="{ invalid: Boolean(error) }">
    <label :for="id || fallback" class="label">{{ label }}</label>
    <slot name="before" />
    <div class="control">
      <input
        :id="id || fallback"
        class="input"
        :class="{ 'dx-plate': plate }"
        :value="modelValue"
        :placeholder="placeholder"
        :autocomplete="autocomplete"
        :dir="plate ? 'ltr' : undefined"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="
          [hint ? `${id || fallback}-hint` : '', error ? `${id || fallback}-error` : '']
            .filter(Boolean)
            .join(' ') || undefined
        "
        v-bind="$attrs"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @blur="emit('blur')"
      />
      <slot name="after" />
    </div>
    <p v-if="hint" :id="`${id || fallback}-hint`" class="hint dx-footnote">{{ hint }}</p>
    <p v-if="error" :id="`${id || fallback}-error`" class="error dx-footnote" role="alert">
      {{ error }}
    </p>
  </div>
</template>

<style scoped>
.field {
  display: grid;
  gap: var(--dx-space-1);
  min-width: 0;
}

.label {
  font-size: var(--dx-text-dense);
  font-weight: var(--dx-weight-label);
}

.control {
  display: flex;
  flex-wrap: wrap;
  gap: var(--dx-space-2);
  align-items: center;
}

.input {
  flex: 1 1 12rem;
  min-width: 0;
  min-height: var(--dx-target);
  padding: 0 var(--dx-space-3);
  border: var(--dx-line) solid var(--dx-border-strong);
  border-radius: var(--dx-radius-control);
  background: var(--dx-surface);
  color: var(--dx-text);
  font-size: var(--dx-text-body);
}

.input::placeholder {
  color: var(--dx-text-3);
}

.input:focus-visible {
  outline: 2px solid var(--dx-focus);
  outline-offset: 2px;
}

.invalid .input {
  border-color: var(--dx-danger);
}

.hint {
  color: var(--dx-text-2);
}

.error {
  color: var(--dx-danger);
}
</style>
