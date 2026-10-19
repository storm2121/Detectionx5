<script setup lang="ts">
import { ref } from 'vue'

import type { Box } from '@/api/types'

/** A photo with the detector's box drawn over it in the photo's own pixel coordinates. */
withDefaults(defineProps<{ src: string; alt: string; box?: Box | null }>(), { box: null })
const emit = defineEmits<{ measure: [width: number, height: number] }>()

const size = ref<{ width: number; height: number } | null>(null)

function onLoad(event: Event) {
  const image = event.target as HTMLImageElement
  size.value = { width: image.naturalWidth, height: image.naturalHeight }
  emit('measure', image.naturalWidth, image.naturalHeight)
}

function span(box: Box, axis: 0 | 1) {
  return Math.max(1, box[axis + 2]! - box[axis]!)
}

defineExpose({ size })
</script>

<template>
  <figure class="thumb" data-testid="photo-frame">
    <img :src="src" :alt="alt" draggable="false" @load="onLoad" />
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
        :width="span(box, 0)"
        :height="span(box, 1)"
        vector-effect="non-scaling-stroke"
      />
      <rect
        class="box"
        :x="box[0]"
        :y="box[1]"
        :width="span(box, 0)"
        :height="span(box, 1)"
        vector-effect="non-scaling-stroke"
      />
    </svg>
    <figcaption v-if="$slots.default"><slot /></figcaption>
  </figure>
</template>

<style scoped>
.thumb {
  position: relative;
  min-width: 0;
  overflow: hidden;
  border-radius: var(--dx-radius-control);
  background: var(--dx-surface-inset);
}

img {
  display: block;
  width: 100%;
  height: auto;
  user-select: none;
  -webkit-user-drag: none;
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
}

.box {
  fill: none;
  stroke: var(--dx-box);
  stroke-width: 2.5;
}

figcaption {
  padding: var(--dx-space-1) 0 0;
  color: var(--dx-text-2);
  font-size: var(--dx-text-caption);
  overflow-wrap: anywhere;
}
</style>
