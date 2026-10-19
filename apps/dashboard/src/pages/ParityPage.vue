<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import SyntheticNote from '@/components/SyntheticNote.vue'
import DxButton from '@/components/ui/DxButton.vue'
import NoticeBlock from '@/components/ui/NoticeBlock.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import StatusLine from '@/components/ui/StatusLine.vue'
import type { Backend } from '@/inference/runtime'
import { useBrowserStore } from '@/stores/browser'

const browser = useBrowserStore()
const gpu = ref(false)

const backends = computed(() => [
  { label: 'WebAssembly (CPU)', value: 'wasm' as Backend },
  ...(gpu.value ? [{ label: 'WebGPU', value: 'webgpu' as Backend }] : []),
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
      <p>
        The in-browser mode reads plates with TypeScript ports of the Python pipeline's image
        operations, decoders and fusion, and ONNX Runtime Web. This page reads the committed
        fixtures (<code>results/parity_fixtures.json</code>: CRNN crops and a three-photo street
        scene set) here and compares every number with what Python recorded.
      </p>
    </header>

    <section class="dx-section" aria-labelledby="run-title">
      <div class="dx-section-head">
        <h2 id="run-title">Run</h2>
        <StatusLine
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
      <div class="dx-row">
        <SegmentedControl v-model="backend" :options="backends" label="Inference backend" />
        <DxButton
          :busy="browser.checking"
          busy-label="Reading the fixtures"
          data-testid="parity-run"
          @click="browser.check()"
        >
          Run again
        </DxButton>
      </div>
      <SkeletonBlock
        v-if="browser.checking"
        kind="table"
        :rows="4"
        label="Reading the fixtures in this browser"
      />
      <NoticeBlock
        v-else-if="browser.parityError"
        tone="error"
        title="The check could not run"
        :message="`${browser.parityError} Reload the page to fetch the models again.`"
      />
      <dl v-if="report && !browser.checking" class="dx-facts" data-testid="parity-maxima">
        <dt>Backend</dt>
        <dd>{{ report.backend === 'webgpu' ? 'WebGPU' : 'WebAssembly' }}</dd>
        <dt>Model</dt>
        <dd>
          <code>{{ report.modelVersion }}</code>
        </dd>
        <dt>Largest input difference</dt>
        <dd>{{ report.maxima.inputLevels }} grey level(s)</dd>
        <dt>Largest logit difference</dt>
        <dd>{{ report.maxima.logits.toExponential(2) }}</dd>
        <dt>Largest probability difference</dt>
        <dd>{{ report.maxima.probability.toExponential(2) }}</dd>
        <dt>Largest box difference</dt>
        <dd>{{ report.maxima.box.toExponential(2) }} px</dd>
        <dt>Largest detector score difference</dt>
        <dd>{{ report.maxima.detectorConfidence.toExponential(2) }}</dd>
        <dt>Time</dt>
        <dd>{{ report.seconds.toFixed(1) }} s for every fixture</dd>
      </dl>
    </section>

    <section v-if="report && !browser.checking" class="dx-section" aria-labelledby="checks-title">
      <h2 id="checks-title">Fixtures</h2>
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
                <StatusLine
                  :tone="check.ok ? 'ok' : 'bad'"
                  :label="check.ok ? 'Within tolerance' : 'Out of tolerance'"
                />
              </td>
              <td class="dx-footnote">{{ check.detail }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <SyntheticNote
      detail="The fixtures are synthetic images; parity says the browser computes what Python computes, not how accurate either is."
    />
  </div>
</template>
