<script setup lang="ts">
import { CircleAlert, CircleCheck, CircleDashed } from '@lucide/vue'
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import DxIcon from '@/components/ui/DxIcon.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import { useBrowserStore } from '@/stores/browser'
import { useReadStore, type ReadMode } from '@/stores/read'

/**
 * Where the plate is read: on the service, or in this browser with ONNX Runtime Web. In the
 * browser the parity check against the Python pipeline runs first, and its outcome is the
 * small check beside the control, linked to the details.
 */
const read = useReadStore()
const browser = useBrowserStore()

const modes = [
  { label: 'Server', value: 'server' as const },
  { label: 'In this browser', value: 'browser' as const },
]

const mode = computed({
  get: () => read.mode,
  set: (value: ReadMode) => {
    read.setMode(value)
    if (value === 'browser') void browser.prepare()
  },
})

const parity = computed(() => {
  const report = browser.parity
  if (browser.parityError) {
    return {
      tone: 'bad',
      icon: CircleAlert,
      text: 'Parity check failed to run',
      short: 'Not checked',
    }
  }
  if (browser.checking || browser.loading) {
    return {
      tone: 'neutral',
      icon: CircleDashed,
      text: 'Checking parity with Python',
      short: 'Checking',
    }
  }
  if (!report) {
    return {
      tone: 'neutral',
      icon: CircleDashed,
      text: 'Parity not checked yet',
      short: 'Not checked',
    }
  }
  const passed = report.checks.filter((c) => c.ok).length
  return report.passed
    ? {
        tone: 'ok',
        icon: CircleCheck,
        text: `parity with Python: ${passed} of ${report.checks.length} fixtures`,
        short: 'Matches Python',
      }
    : {
        tone: 'bad',
        icon: CircleAlert,
        text: `parity off on ${report.checks.length - passed} of ${report.checks.length} fixtures`,
        short: 'Parity off',
      }
})
</script>

<template>
  <div class="mode" data-testid="mode-toggle">
    <div class="control">
      <SegmentedControl v-model="mode" :options="modes" label="Where the plate is read" />
      <RouterLink
        v-if="read.mode === 'browser'"
        to="/parity"
        class="parity"
        :class="parity.tone"
        :title="parity.text"
        data-testid="parity-indicator"
      >
        <DxIcon :icon="parity.icon" :size="16" />
        <span class="dx-sr-only">{{ parity.text }}</span>
        <span aria-hidden="true">{{ parity.short }}</span>
      </RouterLink>
    </div>
    <p v-if="read.mode === 'server'" class="dx-footnote dx-secondary">
      Photos go to the plate service, which stores the read and its crops for review.
    </p>
    <p v-else class="dx-footnote dx-secondary">
      The detector and the recogniser run here with ONNX Runtime Web
      <template v-if="browser.backend"
        >({{ browser.backend === 'webgpu' ? 'WebGPU' : 'WebAssembly' }})</template
      >; no photo leaves this device and nothing is stored.
    </p>
    <p v-if="browser.loadError" class="dx-footnote error" role="alert">
      {{ browser.loadError }} Switch to Server to read on the service instead.
    </p>
  </div>
</template>

<style scoped>
.mode {
  display: grid;
  gap: var(--dx-space-2);
}

.control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--dx-space-2) var(--dx-space-3);
}

.parity {
  display: inline-flex;
  align-items: center;
  gap: var(--dx-space-1);
  min-height: var(--dx-target);
  color: var(--dx-text-2);
  font-size: var(--dx-text-footnote);
  font-weight: var(--dx-weight-label);
  text-decoration: none;
}

.parity:hover {
  text-decoration: underline;
}

.parity.ok :deep(.dx-icon) {
  color: var(--dx-success);
}

.parity.bad {
  color: var(--dx-danger);
}

.error {
  color: var(--dx-danger);
}
</style>
