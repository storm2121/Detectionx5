<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { DetectorEvalResult, EvalResult, TrainingResult } from '@/api/results'
import SimToRealGap from '@/components/SimToRealGap.vue'
import SweepTable, { type SweepResult } from '@/components/SweepTable.vue'
import SyntheticNote from '@/components/SyntheticNote.vue'
import TrainingCurve from '@/components/TrainingCurve.vue'
import NoticeBlock from '@/components/ui/NoticeBlock.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import StatusLine from '@/components/ui/StatusLine.vue'
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
const detectorEval = ref<DetectorEvalResult | null>(null)
const loaded = ref(false)

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
  const index = await results.loadIndex()
  const has = (name: string) => index.some((entry) => entry.name === name)
  training.value = await results.load<TrainingResult>('train_crnn')
  synthetic.value = await results.load<EvalResult>('eval_synthetic')
  pseudoReal.value = await results.load<EvalResult>('eval_pseudo_real')
  if (has('eval_data')) real.value = await results.load<EvalResult>('eval_data')
  if (has('sweep')) sweep.value = await results.load<SweepResult>('sweep')
  if (has('eval_detector_synthetic')) {
    detectorEval.value = await results.load<DetectorEvalResult>('eval_detector_synthetic')
  }
  loaded.value = true
})
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>Models</h1>
      <p>
        How far the recognisers fall from synthetic plates to real photos, what the service runs
        right now, the registry of exported models, and how the recogniser was trained.
      </p>
    </header>

    <section class="dx-section" aria-labelledby="gap-title">
      <div class="dx-section-head">
        <h2 id="gap-title">Real photos: the sim-to-real gap</h2>
        <span class="dx-footnote dx-secondary">exact match, 95% bootstrap intervals</span>
      </div>
      <SkeletonBlock v-if="!loaded" kind="table" :rows="3" label="Loading the results" />
      <template v-else-if="synthetic">
        <p v-if="!real" class="dx-secondary dx-measure">
          The real column fills in once labelled photos are in <code>data/eval</code> and
          <code>uv run plate eval --set data</code> has run.
        </p>
        <SimToRealGap :synthetic="synthetic" :real="real" :pseudo-real="pseudoReal" />
      </template>
    </section>

    <section class="dx-section" aria-labelledby="run-title">
      <div class="dx-section-head">
        <h2 id="run-title">What the service runs</h2>
      </div>
      <SkeletonBlock v-if="!models && !service.modelsError" kind="table" label="Loading models" />
      <NoticeBlock
        v-else-if="service.modelsError"
        tone="error"
        title="Models are unavailable"
        :message="`${service.modelsError} The list returns when the service answers.`"
      />
      <div
        v-if="models"
        class="dx-scroll-x"
        role="region"
        aria-label="Models in service"
        tabindex="0"
      >
        <table class="dx-table facts-table">
          <tbody data-testid="recognizer-card">
            <tr class="group">
              <th scope="rowgroup" colspan="2">
                Recogniser <StatusLine tone="ok" label="Active" />
              </th>
            </tr>
            <tr>
              <th scope="row">Name and version</th>
              <td>
                {{ models.recognizer.name }},
                <code data-testid="model-version">{{ models.recognizer.version }}</code>
              </td>
            </tr>
            <template v-if="metadata">
              <tr>
                <th scope="row">Input</th>
                <td>{{ metadata.input.height }} × {{ metadata.input.width }} px, grey</td>
              </tr>
              <tr>
                <th scope="row">Charset</th>
                <td>
                  {{ metadata.charset.length }} classes, <code>{{ metadata.charset_id }}</code>
                </td>
              </tr>
              <tr>
                <th scope="row">Beam and temperature</th>
                <td>
                  beam width {{ metadata.beam_width }}, T = {{ fixed(metadata.temperature, 4) }}
                </td>
              </tr>
              <tr v-for="[alpha, threshold] in single" :key="alpha">
                <th scope="row">One-view threshold at {{ level(1 - Number(alpha)) }}</th>
                <td>
                  <code>{{ scientific(threshold, 3) }}</code>
                </td>
              </tr>
            </template>
          </tbody>
          <tbody data-testid="detector-card">
            <tr class="group">
              <th scope="rowgroup" colspan="2">
                Detector
                <StatusLine
                  :tone="models.detector.available ? 'ok' : 'warn'"
                  :label="
                    models.detector.available ? 'Active' : 'Missing: photos are read as crops'
                  "
                />
              </th>
            </tr>
            <tr>
              <th scope="row">File and runtime</th>
              <td>
                <code>{{ models.detector.path ?? 'none' }}</code
                >, ONNX Runtime, YOLOv10n with its NMS-free one-to-one head
              </td>
            </tr>
            <template v-if="detectorEval">
              <tr>
                <th scope="row">On synthetic street scenes</th>
                <td data-testid="detector-eval">
                  mAP@50 {{ fixed(detectorEval.metrics.map50, 3) }}, mAP@50-95
                  {{ fixed(detectorEval.metrics.map50_95, 3) }}, precision
                  {{ fixed(detectorEval.metrics.precision, 3) }}, recall
                  {{ fixed(detectorEval.metrics.recall, 3) }} on
                  {{ integer(detectorEval.counts?.images) }} procedural scenes (seed
                  {{ detectorEval.set.seed ?? '?' }}); one Ultralytics pass, so no interval.
                  Synthetic results are not real-world accuracy.
                </td>
              </tr>
            </template>
          </tbody>
          <tbody data-testid="service-card">
            <tr class="group">
              <th scope="rowgroup" colspan="2">Service</th>
            </tr>
            <tr>
              <th scope="row">Fusion</th>
              <td>{{ fusionLabel(models.fusion) }}</td>
            </tr>
            <tr>
              <th scope="row">Served sets</th>
              <td>{{ level(1 - models.alpha) }} level</td>
            </tr>
            <tr>
              <th scope="row">Review</th>
              <td>
                below {{ percent(models.review_threshold, 0) }} confidence, and every read whose set
                is empty or holds several plates
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="fused.length" class="dx-section" aria-labelledby="fused-title">
      <h2 id="fused-title">Thresholds per number of fused views</h2>
      <div class="dx-scroll-x" role="region" aria-label="Fused thresholds" tabindex="0">
        <table class="dx-table">
          <caption>
            The service applies the threshold of the largest calibrated view count not above the
            number of photos that proposed a plate. Fitted on synthetic multi-view sets.
          </caption>
          <thead>
            <tr>
              <th scope="col">Views</th>
              <th v-for="alpha in alphas" :key="alpha" scope="col" class="dx-num">
                {{ level(1 - Number(alpha)) }} level
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="[views, byAlpha] in fused" :key="views">
              <th scope="row">{{ views }} {{ views === '1' ? 'view' : 'views' }}</th>
              <td v-for="alpha in alphas" :key="alpha" class="dx-num">
                <code>{{ scientific(byAlpha[alpha], 2) }}</code>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="models" class="dx-section" aria-labelledby="reg-title">
      <div class="dx-section-head">
        <h2 id="reg-title">Registry</h2>
        <span class="dx-footnote dx-secondary">models/registry.json</span>
      </div>
      <p v-if="registry.models.length === 0" class="dx-secondary">
        Exported models are listed here with their version and results;
        <code>uv run plate registry promote</code> records one.
      </p>
      <div v-else class="dx-scroll-x" role="region" aria-label="Model registry" tabindex="0">
        <table class="dx-table" data-testid="registry-table">
          <thead>
            <tr>
              <th scope="col">Kind</th>
              <th scope="col">Version</th>
              <th scope="col">File</th>
              <th scope="col" class="dx-num">Size</th>
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
              <td class="dx-num">{{ bytes(model.bytes) }}</td>
              <td>{{ Object.keys(model.metrics ?? {}).join(', ') || '–' }}</td>
              <td>
                <StatusLine
                  :tone="isActive(model.kind, model.version) ? 'ok' : 'neutral'"
                  :label="isActive(model.kind, model.version) ? 'Active' : 'Archived'"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="training" class="dx-section" aria-labelledby="train-title">
      <div class="dx-section-head">
        <h2 id="train-title">Training of the CRNN</h2>
        <span class="dx-footnote dx-secondary"
          >model <code>{{ training.model_version }}</code></span
        >
      </div>
      <SyntheticNote detail="The CRNN was trained and validated on synthetic crops only." />
      <div class="training-layout">
        <dl class="dx-facts">
          <dt>Parameters</dt>
          <dd>{{ integer(training.parameters) }}</dd>
          <dt>Epochs</dt>
          <dd>{{ training.history.length }}, kept epoch {{ training.best_epoch }}</dd>
          <dt>Kept on</dt>
          <dd>
            {{ percent(training.best_val_exact_greedy, 1) }} greedy exact match on the synthetic
            validation split, one pass, no interval
          </dd>
          <dt>Device and time</dt>
          <dd>{{ training.device }}, {{ milliseconds(training.seconds * 1000) }}</dd>
          <dt>Real data</dt>
          <dd>{{ training.fine_tuned_on_real_data ? 'fine-tuned on real crops' : 'none used' }}</dd>
          <dt>Seeds</dt>
          <dd>train {{ training.train_seed }}, validation {{ training.val_seed }}</dd>
        </dl>
        <TrainingCurve :history="training.history" :best-epoch="training.best_epoch" />
      </div>
    </section>

    <section v-if="sweep" class="dx-section" aria-labelledby="sweep-title">
      <div class="dx-section-head">
        <h2 id="sweep-title">Domain-randomisation sweep</h2>
        <span class="dx-footnote dx-secondary">results/sweep.json</span>
      </div>
      <SyntheticNote detail="Trials were scored on pseudo-real crops, which are synthetic." />
      <SweepTable :sweep="sweep" />
    </section>
  </div>
</template>

<style scoped>
.facts-table tbody th[scope='row'] {
  width: 16rem;
  color: var(--dx-text-2);
  font-weight: var(--dx-weight-body);
}

.facts-table tr.group th {
  padding-top: var(--dx-space-4);
  border-bottom: var(--dx-line) solid var(--dx-border-strong);
  font-size: var(--dx-text-headline);
  font-weight: var(--dx-weight-title);
}

.facts-table tbody:first-child tr.group th {
  padding-top: 0;
}

.facts-table tr.group :deep(.status) {
  margin-left: var(--dx-space-2);
}

.training-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr);
  gap: var(--dx-space-6);
  align-items: start;
}

@media (max-width: 800px) {
  .training-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
