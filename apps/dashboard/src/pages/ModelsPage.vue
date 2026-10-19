<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { EvalResult, TrainingResult } from '@/api/results'
import ErrorNote from '@/components/ErrorNote.vue'
import LoadingState from '@/components/LoadingState.vue'
import SimToRealGap from '@/components/SimToRealGap.vue'
import StatusPill from '@/components/StatusPill.vue'
import SweepTable, { type SweepResult } from '@/components/SweepTable.vue'
import SyntheticNote from '@/components/SyntheticNote.vue'
import TrainingCurve from '@/components/TrainingCurve.vue'
import { bytes, fixed, integer, level, milliseconds, percent, scientific } from '@/lib/format'
import { fusionLabel } from '@/lib/labels'
import { useResultsStore } from '@/stores/results'
import { useServiceStore } from '@/stores/service'

const service = useServiceStore()
const results = useResultsStore()
const training = ref<TrainingResult | null>(null)
const synthetic = ref<EvalResult | null>(null)
const pseudoReal = ref<EvalResult | null>(null)
const real = ref<EvalResult | null>(null)
const sweep = ref<SweepResult | null>(null)

const models = computed(() => service.models)
const metadata = computed(() => models.value?.recognizer.metadata ?? null)
const single = computed(() =>
  Object.entries(metadata.value?.conformal ?? {}).sort(([a], [b]) => Number(a) - Number(b)),
)
const fused = computed(() =>
  Object.entries(metadata.value?.conformal_fused ?? {}).sort(([a], [b]) => Number(a) - Number(b)),
)
const alphas = computed(() => {
  const keys = new Set<string>()
  for (const [, byAlpha] of fused.value) Object.keys(byAlpha).forEach((k) => keys.add(k))
  return [...keys].sort((a, b) => Number(a) - Number(b))
})
const registry = computed(() => models.value?.registry ?? { models: [], active: {} })

function isActive(kind: string, version: string) {
  return registry.value.active[kind] === version
}

onMounted(async () => {
  void service.loadModels(true)
  training.value = await results.load<TrainingResult>('train_crnn')
  synthetic.value = await results.load<EvalResult>('eval_synthetic')
  pseudoReal.value = await results.load<EvalResult>('eval_pseudo_real')
  const index = await results.loadIndex()
  if (index.some((entry) => entry.name === 'eval_data')) {
    real.value = await results.load<EvalResult>('eval_data')
  }
  if (index.some((entry) => entry.name === 'sweep')) {
    sweep.value = await results.load<SweepResult>('sweep')
  }
})
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>Models</h1>
      <p class="dx-lead">
        What the service runs right now, the registry of exported models, and how the recogniser was
        trained.
      </p>
    </header>

    <SyntheticNote
      detail="The recogniser was trained, calibrated and evaluated on synthetic plates only; no real photo has been used to fit or check it."
    />

    <LoadingState v-if="!models && !service.modelsError" label="Loading models" />
    <ErrorNote
      v-else-if="service.modelsError"
      :message="service.modelsError"
      title="Models are unavailable"
    />

    <div v-if="models" class="dx-grid-3">
      <section class="dx-card" aria-labelledby="rec-title" data-testid="recognizer-card">
        <div class="dx-card-head">
          <h2 id="rec-title">Recogniser</h2>
          <StatusPill tone="ok" label="active" />
        </div>
        <dl class="dx-dl">
          <dt>Name</dt>
          <dd>{{ models.recognizer.name }}</dd>
          <dt>Version</dt>
          <dd>
            <code data-testid="model-version">{{ models.recognizer.version }}</code>
          </dd>
          <template v-if="metadata">
            <dt>Input</dt>
            <dd class="dx-num">{{ metadata.input.height }} × {{ metadata.input.width }} grey</dd>
            <dt>Charset</dt>
            <dd>
              {{ metadata.charset.length }} classes, <code>{{ metadata.charset_id }}</code>
            </dd>
            <dt>Beam width</dt>
            <dd class="dx-num">{{ metadata.beam_width }}</dd>
            <dt>Temperature</dt>
            <dd class="dx-num">{{ fixed(metadata.temperature, 4) }}</dd>
            <template v-for="[alpha, threshold] in single" :key="alpha">
              <dt>Threshold at {{ level(1 - Number(alpha)) }}</dt>
              <dd class="dx-num">
                <code>{{ scientific(threshold, 3) }}</code>
              </dd>
            </template>
          </template>
        </dl>
      </section>

      <section class="dx-card" aria-labelledby="det-title" data-testid="detector-card">
        <div class="dx-card-head">
          <h2 id="det-title">Detector</h2>
          <StatusPill
            :tone="models.detector.available ? 'ok' : 'warn'"
            :label="models.detector.available ? 'active' : 'missing'"
          />
        </div>
        <dl class="dx-dl">
          <dt>File</dt>
          <dd>
            <code>{{ models.detector.path ?? 'none' }}</code>
          </dd>
          <dt>Runtime</dt>
          <dd>ONNX Runtime, NMS-free one-to-one head</dd>
        </dl>
        <p class="dx-small dx-muted note">
          YOLOv10n, one class. Without a detector the service reads every photo as a plate crop.
        </p>
      </section>

      <section class="dx-card" aria-labelledby="svc-title" data-testid="service-card">
        <div class="dx-card-head">
          <h2 id="svc-title">Service</h2>
        </div>
        <dl class="dx-dl">
          <dt>Fusion</dt>
          <dd>{{ fusionLabel(models.fusion) }}</dd>
          <dt>Served sets</dt>
          <dd class="dx-num">{{ level(1 - models.alpha) }} level</dd>
          <dt>Review below</dt>
          <dd class="dx-num">{{ percent(models.review_threshold, 0) }} confidence</dd>
        </dl>
        <p class="dx-small dx-muted note">
          Reads whose set is empty or holds several plates also go to review.
        </p>
      </section>
    </div>

    <section v-if="fused.length" class="dx-card" aria-labelledby="fused-title">
      <div class="dx-card-head">
        <h2 id="fused-title">Thresholds per number of fused views</h2>
      </div>
      <div class="dx-scroll-x" role="region" aria-label="Fused thresholds" tabindex="0">
        <table class="dx-table">
          <caption>
            The service applies the threshold of the largest calibrated view count not above the
            number of photos that proposed a plate (fitted on synthetic multi-view sets).
          </caption>
          <thead>
            <tr>
              <th scope="col">Views</th>
              <th v-for="alpha in alphas" :key="alpha" scope="col" class="dx-right">
                {{ level(1 - Number(alpha)) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="[views, byAlpha] in fused" :key="views">
              <th scope="row" class="dx-num">{{ views }}</th>
              <td v-for="alpha in alphas" :key="alpha" class="dx-right dx-num">
                <code>{{ scientific(byAlpha[alpha], 2) }}</code>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="models" class="dx-card" aria-labelledby="reg-title">
      <div class="dx-card-head">
        <h2 id="reg-title">Registry</h2>
        <span class="dx-small dx-muted">models/registry.json</span>
      </div>
      <p v-if="registry.models.length === 0" class="dx-muted">The registry is empty.</p>
      <div v-else class="dx-scroll-x" role="region" aria-label="Model registry" tabindex="0">
        <table class="dx-table" data-testid="registry-table">
          <thead>
            <tr>
              <th scope="col">Kind</th>
              <th scope="col">Version</th>
              <th scope="col">File</th>
              <th scope="col" class="dx-right">Size</th>
              <th scope="col">Recorded results</th>
              <th scope="col">State</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="model in registry.models" :key="`${model.kind}-${model.version}`">
              <td>{{ model.kind }}</td>
              <td>
                <code>{{ model.version }}</code>
              </td>
              <td>
                <code>{{ model.file }}</code>
              </td>
              <td class="dx-right dx-num nowrap">{{ bytes(model.bytes) }}</td>
              <td class="dx-small">{{ Object.keys(model.metrics ?? {}).join(', ') || '–' }}</td>
              <td>
                <StatusPill
                  :tone="isActive(model.kind, model.version) ? 'ok' : 'neutral'"
                  :label="isActive(model.kind, model.version) ? 'active' : 'archived'"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="synthetic && pseudoReal" class="dx-card" aria-labelledby="gap-title">
      <div class="dx-card-head">
        <h2 id="gap-title">Sim-to-real gap</h2>
        <span class="dx-small dx-muted">exact match, 95% bootstrap intervals</span>
      </div>
      <p class="dx-small dx-muted gap-note">
        The same recognisers on the synthetic test set and on the pseudo-real set (synthetic plates
        under heavier degradations, standing in for real photos). Real photos get their own column
        once a labelled set exists under <code>data/ocr/test</code> and
        <code>plate eval --set data</code> has run.
      </p>
      <SimToRealGap :synthetic="synthetic" :pseudo-real="pseudoReal" :real="real" />
    </section>

    <section v-if="sweep" class="dx-card" aria-labelledby="sweep-title">
      <div class="dx-card-head">
        <h2 id="sweep-title">Domain-randomisation sweep</h2>
        <span class="dx-small dx-muted">results/sweep.json</span>
      </div>
      <SweepTable :sweep="sweep" />
    </section>

    <section v-if="training" class="dx-card" aria-labelledby="train-title">
      <div class="dx-card-head">
        <h2 id="train-title">Training (CRNN)</h2>
        <span class="dx-small dx-muted"
          >model <code>{{ training.model_version }}</code></span
        >
      </div>
      <div class="training-layout">
        <TrainingCurve :history="training.history" :best-epoch="training.best_epoch" />
        <dl class="dx-dl">
          <dt>Parameters</dt>
          <dd class="dx-num">{{ integer(training.parameters) }}</dd>
          <dt>Epochs</dt>
          <dd class="dx-num">{{ training.history.length }}</dd>
          <dt>Best epoch</dt>
          <dd class="dx-num">{{ training.best_epoch }}</dd>
          <dt>Best validation</dt>
          <dd class="dx-num">{{ percent(training.best_val_exact_greedy, 1) }} exact (greedy)</dd>
          <dt>Device</dt>
          <dd>{{ training.device }}</dd>
          <dt>Wall time</dt>
          <dd class="dx-num">{{ milliseconds(training.seconds * 1000) }}</dd>
          <dt>Real data</dt>
          <dd>{{ training.fine_tuned_on_real_data ? 'fine-tuned on real crops' : 'none used' }}</dd>
          <dt>Seeds</dt>
          <dd class="dx-num">
            train {{ training.train_seed }}, validation {{ training.val_seed }}
          </dd>
        </dl>
      </div>
    </section>
  </div>
</template>

<style scoped>
.note {
  margin-top: var(--dx-space-3);
}

.nowrap {
  white-space: nowrap;
}

.gap-note {
  margin-bottom: var(--dx-space-3);
}

.training-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: var(--dx-space-5);
  align-items: start;
}

@media (max-width: 800px) {
  .training-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
