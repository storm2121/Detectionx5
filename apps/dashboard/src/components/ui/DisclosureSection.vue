<script setup lang="ts">
import { ChevronRight } from '@lucide/vue'
import { nextTick, onMounted, ref, useId, watch } from 'vue'

import { vPress } from '@/motion/press'
import { enter, leave, springTo } from '@/motion/springs'

import DxIcon from './DxIcon.vue'

/**
 * A section that opens and closes in place. The content stays in the document (hidden while
 * closed), rises into view when opened and leaves the same way; opening again mid-close
 * picks the content up from where it is. The chevron turns with the same spring.
 */
const props = withDefaults(
  defineProps<{ title: string; summary?: string; open?: boolean; level?: 2 | 3 }>(),
  { summary: '', open: false, level: 3 },
)
const emit = defineEmits<{ 'update:open': [open: boolean] }>()

const id = useId()
const expanded = ref(props.open)
const hidden = ref(!props.open)
const content = ref<HTMLElement | null>(null)
const chevron = ref<HTMLElement | null>(null)
let generation = 0

async function show(next: boolean) {
  const run = ++generation
  if (chevron.value) springTo(chevron.value, { rotate: next ? 90 : 0 })
  if (next) {
    hidden.value = false
    await nextTick()
    if (content.value) enter(content.value)
  } else if (content.value) {
    await leave(content.value)
    if (run === generation) hidden.value = true
  } else {
    hidden.value = true
  }
}

function toggle() {
  expanded.value = !expanded.value
  emit('update:open', expanded.value)
}

watch(expanded, (next) => void show(next))
watch(
  () => props.open,
  (next) => {
    expanded.value = next
  },
)
onMounted(() => {
  if (chevron.value) chevron.value.style.transform = expanded.value ? 'rotate(90deg)' : ''
})
</script>

<template>
  <section class="disclosure">
    <component :is="`h${level}`" class="heading">
      <button
        v-press
        type="button"
        class="toggle"
        :aria-expanded="expanded"
        :aria-controls="id"
        @click="toggle"
      >
        <span ref="chevron" class="chevron"><DxIcon :icon="ChevronRight" :size="16" /></span>
        <span class="title">{{ title }}</span>
        <span v-if="summary" class="summary">{{ summary }}</span>
      </button>
    </component>
    <div :id="id" ref="content" class="content" :hidden="hidden">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.disclosure {
  display: grid;
  min-width: 0;
}

.heading {
  font-size: var(--dx-text-headline);
}

.toggle {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--dx-space-1) var(--dx-space-2);
  width: 100%;
  min-height: var(--dx-target);
  padding: var(--dx-space-2) 0;
  border: 0;
  background: transparent;
  color: var(--dx-text);
  font: inherit;
  font-weight: var(--dx-weight-title);
  text-align: left;
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.chevron {
  display: inline-grid;
  place-items: center;
  align-self: center;
  color: var(--dx-text-2);
}

.summary {
  color: var(--dx-text-2);
  font-size: var(--dx-text-dense);
  font-weight: var(--dx-weight-body);
}

.content {
  min-width: 0;
  padding-top: var(--dx-space-3);
}

.content[hidden] {
  display: none;
}
</style>
