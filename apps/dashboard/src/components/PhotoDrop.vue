<script setup lang="ts">
import { ref } from 'vue'

withDefaults(defineProps<{ disabled?: boolean; maxPhotos?: number }>(), {
  disabled: false,
  maxPhotos: 10,
})
const emit = defineEmits<{ add: [files: File[]] }>()

const over = ref(false)
const input = ref<HTMLInputElement | null>(null)

function onPick(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) emit('add', [...target.files])
  target.value = ''
}

function onDrop(event: DragEvent) {
  over.value = false
  const files = event.dataTransfer?.files
  if (files && files.length > 0) emit('add', [...files])
}
</script>

<template>
  <label
    class="drop"
    :class="{ over, disabled }"
    data-testid="photo-drop"
    @dragenter.prevent="over = true"
    @dragover.prevent="over = true"
    @dragleave.prevent="over = false"
    @drop.prevent="onDrop"
  >
    <input
      ref="input"
      class="dx-sr-only"
      type="file"
      accept="image/png,image/jpeg,image/webp,image/bmp"
      multiple
      :disabled="disabled"
      data-testid="photo-input"
      @change="onPick"
    />
    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M4 16.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5M12 4v11m0-11-4 4m4-4 4 4"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    <span class="title">Drop photos here or <span class="link">choose files</span></span>
    <span class="hint">
      One to {{ maxPhotos }} photos of the same car; each photo is one view of the plate.
    </span>
  </label>
</template>

<style scoped>
.drop {
  display: grid;
  justify-items: center;
  gap: var(--dx-space-1);
  padding: var(--dx-space-5) var(--dx-space-4);
  border: 1.5px dashed var(--dx-border-strong);
  border-radius: var(--dx-radius-m);
  background: var(--dx-surface-sunken);
  text-align: center;
  cursor: pointer;
  transition:
    border-color 120ms ease,
    background-color 120ms ease;
}

.drop:hover,
.drop.over {
  border-color: var(--dx-accent);
  background: var(--dx-accent-soft);
}

.drop:focus-within {
  outline: 2px solid var(--dx-focus);
  outline-offset: 2px;
}

.drop.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.icon {
  width: 28px;
  height: 28px;
  color: var(--dx-accent);
}

.title {
  font-weight: 600;
}

.link {
  color: var(--dx-accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.hint {
  color: var(--dx-text-muted);
  font-size: var(--dx-text-sm);
}
</style>
