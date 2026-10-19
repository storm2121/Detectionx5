<script setup lang="ts">
import { ImagePlus } from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'

import type { Box } from '@/api/types'
import DxButton from '@/components/ui/DxButton.vue'
import DxIcon from '@/components/ui/DxIcon.vue'
import { createSortable } from '@/motion/sortable'
import type { Photo } from '@/stores/read'

import PhotoThumb from './PhotoThumb.vue'

/**
 * The photos of one car and the boxes the detector drew on them. Photos come in by drop or
 * from the file picker; once in the tray they can be put in any order by dragging (or with
 * the arrow keys), which is the order the views are numbered in.
 */
const props = withDefaults(
  defineProps<{
    photos: Photo[]
    boxes?: (Box | null)[]
    disabled?: boolean
    maxPhotos?: number
  }>(),
  { boxes: () => [], disabled: false, maxPhotos: 10 },
)
const emit = defineEmits<{
  add: [files: File[]]
  remove: [id: string]
  move: [from: number, to: number]
  measure: [id: string, width: number, height: number]
}>()

const id = useId()
const over = ref(false)
const grid = ref<HTMLElement | null>(null)
const elements = new Map<string, HTMLElement>()
const dragging = ref<number | null>(null)
const announcement = ref('')
const full = computed(() => props.photos.length >= props.maxPhotos)

function setItem(photoId: string, element: unknown) {
  if (element instanceof HTMLElement) elements.set(photoId, element)
  else elements.delete(photoId)
}

function ordered(): HTMLElement[] {
  return props.photos.flatMap((photo) => {
    const element = elements.get(photo.id)
    return element ? [element] : []
  })
}

function name(index: number) {
  const photo = props.photos[index]
  return photo ? `View ${index + 1}, ${photo.file.name}` : `View ${index + 1}`
}

const sortable = createSortable({
  zone: () => grid.value,
  items: ordered,
  async move(from, to) {
    emit('move', from, to)
    await nextTick()
  },
  onDragChange(index) {
    dragging.value = index
  },
  announce(event, from, to) {
    const count = props.photos.length
    if (event === 'lift') announcement.value = `Picked up ${name(from)}. Move it, then let go.`
    if (event === 'over') announcement.value = `Position ${to + 1} of ${count}.`
    if (event === 'drop') announcement.value = `Moved to position ${to + 1} of ${count}.`
    if (event === 'cancel') announcement.value = `Move cancelled; ${name(from)} stays.`
  },
})

async function onKey(event: KeyboardEvent, index: number) {
  const last = props.photos.length - 1
  const targets: Record<string, number> = {
    ArrowLeft: index - 1,
    ArrowUp: index - 1,
    ArrowRight: index + 1,
    ArrowDown: index + 1,
    Home: 0,
    End: last,
  }
  const target = targets[event.key]
  if (target === undefined || props.disabled) return
  event.preventDefault()
  const clamped = Math.max(0, Math.min(last, target))
  if (clamped === index) return
  const photo = props.photos[index]
  await sortable.moveBy(index, clamped)
  announcement.value = `Moved to position ${clamped + 1} of ${props.photos.length}.`
  if (photo) elements.get(photo.id)?.focus()
}

function onPick(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files.length > 0) emit('add', [...input.files])
  input.value = ''
}

function hasFiles(event: DragEvent) {
  return [...(event.dataTransfer?.types ?? [])].includes('Files')
}

function onDragOver(event: DragEvent) {
  if (!hasFiles(event) || props.disabled) return
  event.preventDefault()
  over.value = true
}

function onDrop(event: DragEvent) {
  over.value = false
  if (!hasFiles(event) || props.disabled) return
  event.preventDefault()
  const files = event.dataTransfer?.files
  if (files && files.length > 0) emit('add', [...files])
}

const touchMove = (event: TouchEvent) => sortable.onTouchMove(event)
onMounted(() => grid.value?.addEventListener('touchmove', touchMove, { passive: false }))
onBeforeUnmount(() => {
  grid.value?.removeEventListener('touchmove', touchMove)
  sortable.dispose()
})
</script>

<template>
  <div
    class="tray"
    :class="{ over }"
    data-testid="photo-drop"
    @dragenter="onDragOver"
    @dragover="onDragOver"
    @dragleave.self="over = false"
    @drop="onDrop"
  >
    <label v-if="!full" class="picker" :class="{ compact: photos.length > 0, disabled }">
      <input
        class="dx-sr-only"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/bmp"
        multiple
        :disabled="disabled"
        data-testid="photo-input"
        @change="onPick"
      />
      <DxIcon :icon="ImagePlus" :size="20" class="picker-icon" />
      <span class="picker-text">
        <span class="picker-title">
          <template v-if="photos.length === 0">Drop photos of one car here, or </template>
          <template v-else>Add more photos, or </template>
          <span class="picker-link">choose files</span>
        </span>
        <span v-if="photos.length === 0" class="picker-hint dx-footnote">
          One to {{ maxPhotos }} photos; each photo is one view of the plate.
        </span>
      </span>
    </label>

    <p v-if="photos.length > 1" :id="`${id}-how`" class="how dx-footnote">
      Drag a photo, or focus it and press the arrow keys, to change the order of the views.
    </p>
    <ol v-if="photos.length" ref="grid" class="grid" data-testid="photos">
      <li
        v-for="(photo, index) in photos"
        :key="photo.id"
        :ref="(element) => setItem(photo.id, element)"
        class="item"
        :class="{ lifted: dragging === index }"
        :tabindex="photos.length > 1 ? 0 : undefined"
        :aria-label="photos.length > 1 ? name(index) : undefined"
        :aria-describedby="photos.length > 1 ? `${id}-how` : undefined"
        @pointerdown="!disabled && sortable.onPointerDown($event, index)"
        @keydown="onKey($event, index)"
        @contextmenu.prevent
      >
        <PhotoThumb
          :src="photo.url"
          :alt="`Photo ${index + 1}, ${photo.file.name}`"
          :box="boxes[index] ?? null"
          @measure="(w: number, h: number) => emit('measure', photo.id, w, h)"
        />
        <div class="caption">
          <span class="caption-text">
            <span class="view">View {{ index + 1 }}</span>
            <span class="file">{{ photo.file.name }}</span>
          </span>
          <DxButton
            variant="plain"
            size="small"
            :disabled="disabled"
            :aria-label="`Remove ${name(index)}`"
            @click="emit('remove', photo.id)"
          >
            Remove
          </DxButton>
        </div>
      </li>
    </ol>
    <p class="dx-sr-only" aria-live="polite">{{ announcement }}</p>
  </div>
</template>

<style scoped>
.tray {
  display: grid;
  gap: var(--dx-space-3);
  min-width: 0;
  border-radius: var(--dx-radius-panel);
}

.picker {
  display: flex;
  align-items: center;
  gap: var(--dx-space-3);
  min-height: 7.5rem;
  padding: var(--dx-space-4) var(--dx-space-5);
  border: var(--dx-line) dashed var(--dx-border-strong);
  border-radius: var(--dx-radius-panel);
  background: var(--dx-surface-inset);
  cursor: pointer;
}

.picker.compact {
  min-height: var(--dx-target);
  padding: var(--dx-space-2) var(--dx-space-4);
}

.picker:hover,
.over .picker {
  border-color: var(--dx-accent);
  background: var(--dx-accent-soft);
}

.picker:focus-within {
  outline: 2px solid var(--dx-focus);
  outline-offset: 2px;
}

.picker.disabled {
  cursor: default;
  opacity: 0.5;
}

.picker-icon {
  color: var(--dx-accent);
}

.picker-text {
  display: grid;
  gap: 2px;
}

.picker-title {
  font-weight: var(--dx-weight-label);
}

.picker-link {
  color: var(--dx-accent);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 0.18em;
}

.picker-hint,
.how {
  color: var(--dx-text-2);
}

.grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 10rem), 1fr));
  gap: var(--dx-space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.item {
  position: relative;
  display: grid;
  align-content: start;
  gap: var(--dx-space-1);
  min-width: 0;
  border-radius: var(--dx-radius-control);
  cursor: grab;
  touch-action: pan-y;
  user-select: none;
  -webkit-touch-callout: none;
  will-change: transform;
}

.item.lifted {
  z-index: 2;
  cursor: grabbing;
}

/* a lifted photo floats above the others: the one in-flow element allowed a shadow */
.item.lifted :deep(.thumb) {
  box-shadow: var(--dx-shadow-float);
}

.caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--dx-space-2);
  min-width: 0;
}

.caption-text {
  display: grid;
  min-width: 0;
}

.view {
  font-size: var(--dx-text-footnote);
  font-weight: var(--dx-weight-label);
}

.file {
  overflow: hidden;
  color: var(--dx-text-2);
  font-family: var(--dx-font-small);
  font-size: var(--dx-text-caption);
  letter-spacing: var(--dx-track-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
