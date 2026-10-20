<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type {
  CalibrationResult,
  DetectorEvalResult,
  EvalResult,
  FusedCalibrationResult,
} from '@/api/results'
import CalibrationCurve from '@/components/CalibrationCurve.vue'
import ConfusionMatrix from '@/components/ConfusionMatrix.vue'
import CoverageTable from '@/components/CoverageTable.vue'
import DetectorComparison from '@/components/DetectorComparison.vue'
import MetricTable from '@/components/MetricTable.vue'
import RealSetFacts from '@/components/RealSetFacts.vue'
import SyntheticNote from '@/components/SyntheticNote.vue'
import NoticeBlock from '@/components/ui/NoticeBlock.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import SelectField from '@/components/ui/SelectField.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { fusedRows, singleViewRows } from '@/lib/coverage'
import { estimate, fixed, interval } from '@/lib/format'
import { countWords, fusionLabel, recognizerLabel, SET_LABELS, setLabel } from '@/lib/labels'
import { useResultsStore } from '@/stores/results'

const route = useRoute()
const router = useRouter()
const results = useResultsStore()

const METRICS = [
  'exact_match',
  'digits_accuracy',
  'letter_accuracy',
  'region_accuracy',
  'format_accuracy',
  'read_rate',
  'cer',
  'ece',
  'mean_confidence',
  'coverage',
  'set_size',
]
const REAL_METRICS = [
  'exact_match',
  'digits_accuracy',
  'letter_accuracy',
  'region_accuracy',
  'read_rate',
  'cer',
  'ece',
  'coverage',
]

const indexLoaded = ref(false)
const available = ref<string[]>([])
const real = ref<EvalResult | null>(null)
const endToEnd = ref<EvalResult | null>(null)
const detectorReal = ref<DetectorEvalResult | null>(null)
const detectorSynthetic = ref<DetectorEvalResult | null>(null)
const realFocus = ref<string>('crnn-beam')
const chosen = ref<string>(typeof route.query.set === 'string' ? route.query.set : 'eval_synthetic')
const evaluation = ref<EvalResult | null>(null)
const loading = ref(false)
const focus = ref<string>('crnn-beam')
const calibration = ref<CalibrationResult | null>(null)
const fused = ref<FusedCalibrationResult | null>(null)

const setOptions = computed(() =>
  available.value.map((name) => ({ label: setLabel(name), value: name })),
)
const options = (payload: EvalResult | null) =>
  Object.keys(payload?.recognizers ?? {}).map((name) => ({
    label: recognizerLabel(name),
    value: name,
  }))
const columns = (payload: EvalResult | null) =>
  Object.fromEntries(
    Object.entries(payload?.recognizers ?? {}).map(([name, r]) => [name, r.metrics]),
  )
const comparisons = (payload: EvalResult | null) =>
  Object.entries(payload?.comparisons ?? {}).flatMap(([pair, stats]) => {
    const difference = stats.exact_match_difference
    return difference ? [{ pair, difference }] : []
  })

const realFocused = computed(() => real.value?.recognizers[realFocus.value] ?? null)
const detectionSentence = computed(() => {
  const detection = endToEnd.value?.detection
  if (!detection) return ''
  const missed = countWords(detection.no_detection)
  const head =
    `${missed.charAt(0).toUpperCase()}${missed.slice(1)} photos had no detection and in ` +
    `${countWords(detection.off_plate)} more the most confident detection was not on the ` +
    'labelled plate; both count as wrong reads.'
  return `${head} The most confident detection lay on the labelled plate in ${estimate(detection.on_plate, false, 0)} of the photos.`
})
const focused = computed(() => evaluation.value?.recognizers[focus.value] ?? null)
const error = computed(() => results.errors[chosen.value] ?? results.errors.index ?? null)

const fusion = computed(() => {
  const section = evaluation.value?.fusion
  const entry = section?.recognizers[focus.value]
  if (!section || !entry) return null
  return {
    k: section.k,
    nSets: section.n_sets,
    methods: Object.entries(entry.methods).map(([method, byK]) => ({
      method,
      cells: section.k.map((k) => byK[`k=${k}`]?.metrics.exact_match ?? null),
    })),
  }
})

const singleRows = computed(() => (calibration.value ? singleViewRows(calibration.value) : []))
const multiRows = computed(() => (fused.value ? fusedRows(fused.value) : []))

function points(value: number, low: number, high: number) {
  const p = (v: number) => `${v > 0 ? '+' : ''}${(v * 100).toFixed(0)}`
  return `${p(value)} points (${p(low)} to ${p(high)})`
}

async function loadSet(name: string) {
  loading.value = true
  evaluation.value = await results.load<EvalResult>(name)
  loading.value = false
  const names = Object.keys(evaluation.value?.recognizers ?? {})
  if (evaluation.value && !(focus.value in evaluation.value.recognizers)) {
    focus.value = names.includes('crnn-beam') ? 'crnn-beam' : (names[0] ?? '')
  }
}

watch(chosen, (name) => {
  void router.replace({ query: { ...route.query, set: name } })
  void loadSet(name)
})

onMounted(async () => {
  const index = await results.loadIndex()
  indexLoaded.value = true
  const has = (name: string) => index.some((entry) => entry.name === name)
  if (has('eval_data')) real.value = await results.load<EvalResult>('eval_data')
  if (has('eval_data_e2e')) endToEnd.value = await results.load<EvalResult>('eval_data_e2e')
  if (has('eval_detector_data')) {
    detectorReal.value = await results.load<DetectorEvalResult>('eval_detector_data')
  }
  if (has('eval_detector_synthetic')) {
    detectorSynthetic.value = await results.load<DetectorEvalResult>('eval_detector_synthetic')
  }
  available.value = index
    .map((entry) => entry.name)
    .filter((name) => name in SET_LABELS)
    .sort((a, b) => Object.keys(SET_LABELS).indexOf(a) - Object.keys(SET_LABELS).indexOf(b))
  if (!available.value.includes(chosen.value) && available.value[0]) {
    chosen.value = available.value[0]
  } else {
    void loadSet(chosen.value)
  }
  calibration.value = await results.load<CalibrationResult>('calibration_crnn')
  fused.value = await results.load<FusedCalibrationResult>('calibration_fused')
})
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>Evaluation</h1>
      <p>
        Every recogniser on labelled real photos first, then on the synthetic sets the models are
        developed against, each number with its 95% bootstrap interval. Everything here is read from
        <code>results/*.json</code>; nothing is typed by hand.
      </p>
    </header>

    <section class="dx-section" aria-labelledby="real-title" data-testid="real-photos">
      <div class="dx-section-head">
        <h2 id="real-title">Real photos</h2>
        <span v-if="real" class="dx-footnote dx-secondary">data/eval, private</span>
      </div>
      <SkeletonBlock v-if="!indexLoaded" kind="table" label="Loading the real-photo results" />
      <template v-else-if="real">
        <RealSetFacts :real="real" />
        <div class="dx-columns real-tables">
          <div class="dx-stack" data-testid="real-labelled">
            <h3>From the labelled box</h3>
            <p class="dx-footnote dx-secondary">
              {{ real.set.n }} plates in {{ real.set.photos ?? real.set.n }} photos, each cut where
              the service would cut a detection of it.
            </p>
            <MetricTable
              :columns="columns(real)"
              :metrics="REAL_METRICS"
              :column-label="recognizerLabel"
              :digits="0"
              :caption="`From the labelled box, n = ${real.set.n} plates; letter and region on the standard plates only.`"
            />
          </div>
          <div v-if="endToEnd" class="dx-stack" data-testid="real-end-to-end">
            <h3>End to end with the detector</h3>
            <p class="dx-footnote dx-secondary" data-testid="detection-summary">
              {{ endToEnd.set.n }} photos, the labelled boxes ignored: each photo's most confident
              detection is read as the service reads it. {{ detectionSentence }}
            </p>
            <MetricTable
              :columns="columns(endToEnd)"
              :metrics="REAL_METRICS"
              :column-label="recognizerLabel"
              :digits="0"
              :caption="`End to end, n = ${endToEnd.set.n} photos; letter and region on the photos with a standard plate.`"
            />
          </div>
        </div>
        <ul v-if="comparisons(real).length" class="comparisons dx-footnote">
          <li v-for="item in comparisons(real)" :key="item.pair">
            {{ item.pair.split(' - ').map(recognizerLabel).join(' minus ') }}, exact match from the
            labelled box:
            {{ points(item.difference.value, item.difference.ci_low, item.difference.ci_high) }},
            paired over the same plates
          </li>
        </ul>
        <div v-if="detectorReal" class="dx-stack">
          <h3>The detector on these photos</h3>
          <p v-if="detectorReal.note" class="dx-footnote dx-secondary dx-measure">
            {{ `${detectorReal.note.charAt(0).toUpperCase()}${detectorReal.note.slice(1)}.` }}
          </p>
          <DetectorComparison
            :real="detectorReal"
            :synthetic="detectorSynthetic"
            :overlap="real.set.card?.detector_overlap"
          />
        </div>
        <div class="charts-head">
          <h3>Calibration and confusions on the real photos</h3>
          <SelectField
            v-model="realFocus"
            :options="options(real)"
            label="Recogniser"
            inline
            data-testid="real-recognizer-choice"
          />
        </div>
        <div v-if="realFocused" class="dx-columns">
          <CalibrationCurve
            :bins="realFocused.reliability"
            :ece="realFocused.metrics.ece?.value ?? null"
            :title="`Reliability of ${recognizerLabel(realFocus)} on real photos`"
          />
          <ConfusionMatrix
            :confusion="realFocused.letter_confusion"
            caption="Letters on the real photos: rows are the true letter, columns the letter read."
          />
        </div>
        <p class="dx-footnote dx-secondary dx-measure" data-testid="calibration-note">
          The calibration remains synthetic: the temperature and the conformal thresholds were
          fitted on synthetic plates and were not refitted on these photos, which are the reporting
          set. On real plates neither holds, which is what these numbers show; a separate real
          calibration split comes next.
        </p>
      </template>
      <p v-else class="dx-secondary dx-measure">
        Results on real photos appear here once labelled photos are in <code>data/eval</code>: run
        <code>uv run plate eval --set data</code>.
      </p>
    </section>

    <section class="dx-section dev" aria-labelledby="dev-title">
      <div class="dx-section-head">
        <h2 id="dev-title">Development and synthetic harness</h2>
      </div>
      <SyntheticNote
        detail="Every set here comes from plate_reader.synthetic; the pseudo-real set is synthetic too, with heavier degradations standing in for real photos."
      />
      <div class="set-choice">
        <SegmentedControl
          v-if="setOptions.length"
          v-model="chosen"
          :options="setOptions"
          label="Evaluation set"
          data-testid="set-choice"
        />
        <NoticeBlock
          v-if="error"
          tone="error"
          title="Results are unavailable"
          :message="`${error} The console reads them from the service; check that it is running.`"
        />
        <SkeletonBlock
          v-else-if="loading || !evaluation"
          kind="lines"
          :lines="1"
          label="Loading results"
        />
        <p v-else class="dx-footnote dx-secondary set-info">
          {{ setLabel(chosen) }}: n = {{ evaluation.set.n }} images{{
            evaluation.set.n_sets
              ? ` in ${evaluation.set.n_sets} sets of ${evaluation.set.k} views`
              : ''
          }}, generator seed {{ evaluation.set.seed }} (version
          {{ evaluation.set.generator_version }}); {{ evaluation.bootstrap.resamples }}
          {{ evaluation.bootstrap.method }} bootstrap resamples over
          {{ evaluation.bootstrap.unit }}s.
        </p>
      </div>

      <template v-if="evaluation && !loading">
        <div class="dx-section">
          <h3>Recognisers</h3>
          <MetricTable
            :columns="columns(evaluation)"
            :metrics="METRICS"
            :column-label="recognizerLabel"
            :caption="`${setLabel(chosen)}, one read per image; synthetic results are not real-world accuracy.`"
          />
          <ul v-if="comparisons(evaluation).length" class="comparisons dx-footnote">
            <li v-for="item in comparisons(evaluation)" :key="item.pair">
              {{ item.pair.split(' - ').map(recognizerLabel).join(' minus ') }}, exact match:
              {{ fixed(item.difference.value * 100, 1) }} points {{ interval(item.difference) }},
              paired over the same images
            </li>
          </ul>
        </div>

        <div class="dx-section">
          <div class="charts-head">
            <h3>Calibration and confusions</h3>
            <SelectField
              v-model="focus"
              :options="options(evaluation)"
              label="Recogniser"
              inline
              data-testid="recognizer-choice"
            />
          </div>
          <div v-if="focused" class="dx-columns">
            <CalibrationCurve
              :bins="focused.reliability"
              :ece="focused.metrics.ece?.value ?? null"
              :title="`Reliability of ${recognizerLabel(focus)}`"
            />
            <ConfusionMatrix :confusion="focused.letter_confusion" />
          </div>
          <p v-if="focused && !focused.calibrated" class="dx-footnote dx-secondary dx-measure">
            This recogniser's confidence is not a calibrated probability (EasyOCR's vote share), so
            its reliability curve is expected to sit off the diagonal.
          </p>
        </div>

        <div v-if="fusion" class="dx-section">
          <h3>Multi-view fusion, {{ recognizerLabel(focus) }}</h3>
          <div class="dx-scroll-x" role="region" aria-label="Fusion comparison" tabindex="0">
            <table class="dx-table" data-testid="fusion-comparison">
              <caption>
                Exact match of the fused read when the first k views of each of
                {{
                  fusion.nSets
                }}
                synthetic multi-view sets are fused, with 95% bootstrap intervals over sets.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Method</th>
                  <th v-for="k in fusion.k" :key="k" scope="col">
                    {{ k }} {{ k === 1 ? 'view' : 'views' }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in fusion.methods" :key="row.method">
                  <th scope="row">{{ fusionLabel(row.method) }}</th>
                  <td v-for="(cell, i) in row.cells" :key="i">
                    {{ cell ? estimate(cell) : '–' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <div v-if="calibration" class="dx-section">
        <div class="dx-section-head">
          <h3>Temperature scaling of the CRNN</h3>
          <span class="dx-footnote dx-secondary"
            >model <code>{{ calibration.model_version }}</code></span
          >
        </div>
        <p class="dx-footnote dx-secondary dx-measure">
          Temperature T = {{ fixed(calibration.temperature.temperature, 3) }}, fitted on
          {{ calibration.splits.calibration?.n }} synthetic calibration crops (negative
          log-likelihood {{ fixed(calibration.temperature.nll_before, 4) }} before and
          {{ fixed(calibration.temperature.nll_after, 4) }} after); expected calibration error on
          the separate test split {{ estimate(calibration.test_split.ece, false, 2) }}.
        </p>
        <div class="dx-columns">
          <CalibrationCurve
            :bins="calibration.calibration_split.before.reliability"
            :ece="calibration.calibration_split.before.ece.value"
            title="Before temperature scaling (calibration split)"
          />
          <CalibrationCurve
            :bins="calibration.calibration_split.after.reliability"
            :ece="calibration.calibration_split.after.ece.value"
            title="After temperature scaling (calibration split)"
          />
        </div>
      </div>

      <div v-if="calibration || fused" class="dx-section">
        <h3>Conformal sets</h3>
        <CoverageTable
          v-if="singleRows.length"
          :rows="singleRows"
          caption="One view: thresholds fitted on the conformal split, coverage on the test split, with a joint bootstrap over both."
        />
        <CoverageTable
          v-if="multiRows.length"
          :rows="multiRows"
          caption="Fused reads: one threshold per number of views, fitted on separate synthetic multi-view calibration sets."
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.dev {
  padding-top: var(--dx-space-6);
  border-top: var(--dx-line) solid var(--dx-border);
}

.set-choice {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--dx-space-3);
}

.charts-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--dx-space-2) var(--dx-space-4);
}

.real-tables h3 {
  margin: 0;
}

.real-tables p {
  margin: 0;
}

.comparisons {
  display: grid;
  gap: var(--dx-space-1);
  margin: 0;
  padding-left: var(--dx-space-4);
  color: var(--dx-text-2);
}
</style>
