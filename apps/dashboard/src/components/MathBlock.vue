<script setup lang="ts">
import 'katex/dist/katex.min.css'

import katex from 'katex'
import { computed } from 'vue'

const props = withDefaults(defineProps<{ tex: string; display?: boolean }>(), { display: true })

// The TeX is authored in this app (the Methods page), never taken from a user or a
// response, and KaTeX runs with `trust: false`, so the generated markup is safe to insert.
const html = computed(() =>
  katex.renderToString(props.tex, {
    displayMode: props.display,
    throwOnError: false,
    output: 'htmlAndMathml',
    strict: 'ignore',
    trust: false,
  }),
)
</script>

<template>
  <!-- A wide equation scrolls on a phone, so it takes keyboard focus to scroll too. -->
  <!-- eslint-disable vue/no-v-html -->
  <div
    v-if="display"
    class="math"
    data-testid="math"
    role="group"
    aria-label="Equation"
    tabindex="0"
    v-html="html"
  />
  <span v-else class="math-inline" v-html="html" />
  <!-- eslint-enable vue/no-v-html -->
</template>

<style scoped>
.math {
  overflow-x: auto;
  overflow-y: hidden;
  padding: var(--dx-space-2) 0;
  max-width: 100%;
}

.math :deep(.katex-display) {
  margin: 0;
}

.math :deep(.katex) {
  font-size: 1.08em;
}
</style>
