<script setup lang="ts">
import { ref } from 'vue'

import type { Box } from '@/api/types'

withDefaults(
  defineProps<{
    src: string
    alt: string
    /** Detected plate in the photo's pixel coordinates. */
    box?: Box | null
    badge?: string
    removable?: boolean
  }>(),
  { box: null, badge: '', removable: false },
)
const emit = defineEmits<{ measure: [width: number, height: number]; remove: [] }>()

const size = ref<{ width: number; height: number } | null>(null)

function onLoad(event: Event) {
  const image = event.target as HTMLImageElement
  size.value = { width: image.naturalWidth, height: image.naturalHeight }
  emit('measure', image.naturalWidth, image.naturalHeight)
}

function width(box: Box) {
  return Math.max(1, box[2] - box[0])
}

function height(box: Box) {
  return Math.max(1, box[3] - box[1])
}

defineExpose({ size })
</script>

<template>
  <figure class="frame" data-testid="photo-frame">
    <div class="canvas">
      <img :src="src" :alt="alt" @load="onLoad" />
      <svg
        v-if="box && size"
        class="overlay"
        :viewBox="`0 0 ${size.width} ${size.height}`"
        preserveAspectRatio="none"
        aria-hidden="true"
        data-testid="plate-box"
      >
        <rect
          class="halo"
          :x="box[0]"
          :y="box[1]"
          :width="width(box)"
          :height="height(box)"
          vector-effect="non-scaling-stroke"
        />
        <rect
          class="box"
          :x="box[0]"
          :y="box[1]"
          :width="width(box)"
          :height="height(box)"
          vector-effect="non-scaling-stroke"
        />
      </svg>
      <span v-if="badge" class="badge">{{ badge }}</span>
      <button
        v-if="removable"
        type="button"
        class="remove"
        :aria-label="`Remove ${alt}`"
        @click="emit('remove')"
      >
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path
            d="M4 4l8 8M12 4l-8 8"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          />
        </svg>
      </button>
    </div>
    <figcaption v-if="$slots.default"><slot /></figcaption>
  </figure>
</template>

<style scoped>
.frame {
  margin: 0;
  display: grid;
  gap: var(--dx-space-1);
  min-width: 0;
}

.canvas {
  position: relative;
  border-radius: var(--dx-radius-m);
  overflow: hidden;
  background: var(--dx-surface-sunken);
  border: 1px solid var(--dx-border);
}

img {
  display: block;
  width: 100%;
  height: auto;
}

.overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.halo {
  fill: none;
  stroke: var(--dx-box-halo);
  stroke-width: 5;
  stroke-opacity: 0.7;
}

.box {
  fill: none;
  stroke: var(--dx-box);
  stroke-width: 2.5;
}

.badge {
  position: absolute;
  top: 6px;
  left: 6px;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgb(2 6 23 / 0.78);
  color: #ffffff;
  font-size: var(--dx-text-xs);
  font-weight: 600;
}

.remove {
  position: absolute;
  top: 6px;
  right: 6px;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  background: rgb(2 6 23 / 0.78);
  color: #ffffff;
  cursor: pointer;
}

.remove svg {
  width: 14px;
  height: 14px;
}

figcaption {
  font-size: var(--dx-text-xs);
  color: var(--dx-text-muted);
  overflow-wrap: anywhere;
}
</style>
