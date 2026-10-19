<script setup lang="ts">
import Button from 'primevue/button'
import SelectButton from 'primevue/selectbutton'
import { computed, onMounted, ref } from 'vue'

import ErrorNote from '@/components/ErrorNote.vue'
import LoadingState from '@/components/LoadingState.vue'
import StatusPill from '@/components/StatusPill.vue'
import SyntheticNote from '@/components/SyntheticNote.vue'
import type { Backend } from '@/inference/runtime'
import { useBrowserStore } from '@/stores/browser'

const browser = useBrowserStore()
const gpu = ref(false)

const backends = computed(() => [
  { label: 'WebAssembly (CPU)', value: 'wasm' },
  ...(gpu.value ? [{ label: 'WebGPU', value: 'webgpu' }] : []),
])
const backend = computed({
  get: () => browser.backend ?? 'wasm',
  set: (value: Backend) => {
    browser.useBackend(value)
    void browser.check()
  },
})
const report = computed(() => browser.parity)
const passed = computed(() => report.value?.checks.filter((c) => c.ok).length ?? 0)

onMounted(async () => {
  const { webgpuAvailable } = await import('@/inference/runtime')
  gpu.value = await webgpuAvailable()
  if (!browser.backend) browser.useBackend('wasm')
  if (!browser.parity) await browser.check()
})
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>Browser parity</h1>
      <p class="dx-lead">
        The in-browser mode reads plates with TypeScript ports of the Python pipeline's image
        operations, decoders and fusion, and ONNX Runtime Web. This page reads the committed
        fixtures (<code>results/parity_fixtures.json</code>: CRNN crops and a three-photo street
        scene set) here and compares every number with what Python recorded.
      </p>
    </header>

    <SyntheticNote
      detail="The fixtures are synthetic images; parity says the browser computes what Python computes, not how accurate either is."
    />

    <section class="dx-card" aria-labelledby="run-title">
      <div class="dx-card-head">
        <h2 id="run-title">Run</h2>
        <StatusPill
          v-if="report"
          :tone="report.passed ? 'ok' : 'bad'"
          :label="
            report.passed
              ? `passed: ${passed} of ${report.checks.length}`
              : `failed: ${report.checks.length - passed} of ${report.checks.length}`
          "
          data-testid="parity-summary"
        />
      </div>
      <div class="dx-row controls">
        <SelectButton
          v-model="backend"
          :options="backends"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-label="Inference backend"
        />
        <Button
          label="Run again"
          severity="secondary"
          :loading="browser.checking"
          data-testid="parity-run"
          @click="browser.check()"
        />
      </div>
      <LoadingState v-if="browser.checking" label="Reading the fixtures in this browser" />
      <ErrorNote
        v-else-if="browser.parityError"
        :message="browser.parityError"
        title="The check could not run"
      />
      <dl v-if="report && !browser.checking" class="dx-dl maxima" data-testid="parity-maxima">
        <dt>Backend</dt>
        <dd>{{ report.backend === 'webgpu' ? 'WebGPU' : 'WebAssembly' }}</dd>
        <dt>Model</dt>
        <dd>
          <code>{{ report.modelVersion }}</code>
        </dd>
        <dt>Largest input difference</dt>
        <dd class="dx-num">{{ report.maxima.inputLevels }} grey level(s)</dd>
        <dt>Largest logit difference</dt>
        <dd class="dx-num">{{ report.maxima.logits.toExponential(2) }}</dd>
        <dt>Largest probability difference</dt>
        <dd class="dx-num">{{ report.maxima.probability.toExponential(2) }}</dd>
        <dt>Largest box difference</dt>
        <dd class="dx-num">{{ report.maxima.box.toExponential(2) }} px</dd>
        <dt>Largest detector score difference</dt>
        <dd class="dx-num">{{ report.maxima.detectorConfidence.toExponential(2) }}</dd>
        <dt>Time</dt>
        <dd class="dx-num">{{ report.seconds.toFixed(1) }} s</dd>
      </dl>
    </section>

    <section v-if="report && !browser.checking" class="dx-card" aria-labelledby="checks-title">
      <h2 id="checks-title" class="checks-title">Fixtures</h2>
      <div class="dx-scroll-x" role="region" aria-label="Parity checks" tabindex="0">
        <table class="dx-table" data-testid="parity-table">
          <thead>
            <tr>
              <th scope="col">Fixture</th>
              <th scope="col">Result</th>
              <th scope="col">Differences</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="check in report.checks" :key="check.name" :data-ok="check.ok">
              <th scope="row">{{ check.name }}</th>
              <td>
                <StatusPill
                  :tone="check.ok ? 'ok' : 'bad'"
                  :label="check.ok ? 'within tolerance' : 'out of tolerance'"
                />
              </td>
              <td class="dx-small dx-num">{{ check.detail }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.controls {
  margin-bottom: var(--dx-space-3);
}

.maxima {
  margin-top: var(--dx-space-2);
}

.checks-title {
  margin-bottom: var(--dx-space-3);
}
</style>
