<script setup lang="ts">
import SelectButton from 'primevue/selectbutton'
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import StatusPill from '@/components/StatusPill.vue'
import { useBrowserStore } from '@/stores/browser'
import { useReadStore } from '@/stores/read'

const read = useReadStore()
const browser = useBrowserStore()

const modes = [
  { label: 'Server', value: 'server' },
  { label: 'In this browser', value: 'browser' },
]

const mode = computed({
  get: () => read.mode,
  set: (value: 'server' | 'browser') => {
    read.setMode(value)
    if (value === 'browser') void browser.prepare()
  },
})

const parity = computed(() => {
  const report = browser.parity
  if (browser.parityError) return { tone: 'bad' as const, label: 'parity check failed to run' }
  if (browser.checking) return { tone: 'neutral' as const, label: 'checking parity…' }
  if (!report) return { tone: 'neutral' as const, label: 'parity not checked yet' }
  const passed = report.checks.filter((c) => c.ok).length
  return report.passed
    ? {
        tone: 'ok' as const,
        label: `parity with Python: ${passed} of ${report.checks.length} fixtures`,
      }
    : {
        tone: 'bad' as const,
        label: `parity off on ${report.checks.length - passed} of ${report.checks.length} fixtures`,
      }
})
</script>

<template>
  <div class="mode" data-testid="mode-toggle">
    <SelectButton
      v-model="mode"
      :options="modes"
      option-label="label"
      option-value="value"
      :allow-empty="false"
      aria-label="Where the plate is read"
    />
    <p v-if="read.mode === 'server'" class="dx-small dx-muted">
      Photos are sent to the plate service, which stores the read and its crops.
    </p>
    <div v-else class="browser">
      <p class="dx-small dx-muted">
        The detector and the recogniser run here through ONNX Runtime Web
        <template v-if="browser.backend"
          >({{ browser.backend === 'webgpu' ? 'WebGPU' : 'WebAssembly' }})</template
        >; no photo leaves this device and nothing is stored.
      </p>
      <p v-if="browser.loadError" class="dx-small error" role="alert">{{ browser.loadError }}</p>
      <div class="dx-row">
        <StatusPill :tone="parity.tone" :label="parity.label" data-testid="parity-indicator" />
        <RouterLink to="/parity" class="dx-small">details</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mode {
  display: grid;
  gap: var(--dx-space-2);
}

.browser {
  display: grid;
  gap: var(--dx-space-2);
}

.error {
  color: var(--dx-bad);
}
</style>
