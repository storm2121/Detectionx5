import type { Meta, StoryObj } from '@storybook/vue3'

import type {
  CalibrationResult,
  DetectorEvalResult,
  EvalResult,
  FusedCalibrationResult,
  TrainingResult,
} from '@/api/results'
import { fusedRows, singleViewRows } from '@/lib/coverage'
import { recognizerLabel } from '@/lib/labels'
import calibration from '@results/calibration_crnn.json'
import fused from '@results/calibration_fused.json'
import real from '@results/eval_data.json'
import endToEnd from '@results/eval_data_e2e.json'
import detectorReal from '@results/eval_detector_data.json'
import detectorSynthetic from '@results/eval_detector_synthetic.json'
import pseudo from '@results/eval_pseudo_real.json'
import synthetic from '@results/eval_synthetic.json'
import sweep from '@results/sweep.json'
import training from '@results/train_crnn.json'

import CalibrationCurve from './CalibrationCurve.vue'
import ConfusionMatrix from './ConfusionMatrix.vue'
import CoverageTable from './CoverageTable.vue'
import DetectorComparison from './DetectorComparison.vue'
import MathBlock from './MathBlock.vue'
import MetricTable from './MetricTable.vue'
import RealSetFacts from './RealSetFacts.vue'
import SimToRealGap from './SimToRealGap.vue'
import SweepTable, { type SweepResult } from './SweepTable.vue'
import SyntheticNote from './SyntheticNote.vue'
import TrainingCurve from './TrainingCurve.vue'

// The committed results files. eval_data.json, eval_data_e2e.json and eval_detector_data.json
// hold the labelled real photos (metrics and counts only); every other file is synthetic, and
// synthetic results are not real-world accuracy.
const SYNTHETIC = synthetic as unknown as EvalResult
const PSEUDO = pseudo as unknown as EvalResult
const REAL = real as unknown as EvalResult
const END_TO_END = endToEnd as unknown as EvalResult
const DETECTOR_REAL = detectorReal as unknown as DetectorEvalResult
const DETECTOR_SYNTHETIC = detectorSynthetic as unknown as DetectorEvalResult
const CALIBRATION = calibration as unknown as CalibrationResult
const FUSED = fused as unknown as FusedCalibrationResult
const TRAINING = training as unknown as TrainingResult

const meta: Meta = { title: 'Results' }
export default meta
type Story = StoryObj

const columns = (payload: EvalResult) =>
  Object.fromEntries(Object.entries(payload.recognizers).map(([name, r]) => [name, r.metrics]))

export const RealPhotosTable: Story = {
  render: () => ({
    components: { MetricTable },
    setup: () => ({ columns: columns(REAL), recognizerLabel }),
    template: `<MetricTable :columns="columns" :metrics="['exact_match', 'digits_accuracy', 'letter_accuracy', 'region_accuracy', 'cer', 'ece', 'coverage']" :column-label="recognizerLabel" :digits="0" caption="From the labelled box, n = ${REAL.set.n} plates" />`,
  }),
}

export const RealPhotosEndToEnd: Story = {
  render: () => ({
    components: { MetricTable },
    setup: () => ({ columns: columns(END_TO_END), recognizerLabel }),
    template: `<MetricTable :columns="columns" :metrics="['exact_match', 'digits_accuracy', 'letter_accuracy', 'region_accuracy', 'read_rate', 'cer']" :column-label="recognizerLabel" :digits="0" caption="End to end, n = ${END_TO_END.set.n} photos" />`,
  }),
}

export const RealSet: Story = {
  render: () => ({
    components: { RealSetFacts },
    setup: () => ({ real: REAL }),
    template: '<RealSetFacts :real="real" />',
  }),
}

export const DetectorOnRealPhotos: Story = {
  render: () => ({
    components: { DetectorComparison },
    setup: () => ({
      real: DETECTOR_REAL,
      synthetic: DETECTOR_SYNTHETIC,
      overlap: REAL.set.card?.detector_overlap,
    }),
    template: '<DetectorComparison :real="real" :synthetic="synthetic" :overlap="overlap" />',
  }),
}

export const SyntheticTable: Story = {
  render: () => ({
    components: { MetricTable, SyntheticNote },
    setup: () => ({ columns: columns(PSEUDO), recognizerLabel }),
    template: `<div style="display: grid; gap: 16px">
      <SyntheticNote detail="Pseudo-real crops are synthetic." />
      <MetricTable :columns="columns" :metrics="['exact_match', 'cer', 'ece', 'coverage', 'set_size']" :column-label="recognizerLabel" caption="Pseudo-real set" />
    </div>`,
  }),
}

export const SimToReal: Story = {
  render: () => ({
    components: { SimToRealGap },
    setup: () => ({ synthetic: SYNTHETIC, real: REAL, pseudo: PSEUDO }),
    template: '<SimToRealGap :synthetic="synthetic" :real="real" :pseudo-real="pseudo" />',
  }),
}

export const ReliabilityCalibrated: Story = {
  render: () => ({
    components: { CalibrationCurve },
    setup: () => ({ r: SYNTHETIC.recognizers['crnn-beam'] }),
    template:
      '<CalibrationCurve :bins="r.reliability" :ece="r.metrics.ece.value" title="CRNN, constrained beam, synthetic test set" />',
  }),
}

export const ReliabilityOnRealPhotos: Story = {
  render: () => ({
    components: { CalibrationCurve },
    setup: () => ({ r: REAL.recognizers['crnn-beam'] }),
    template:
      '<CalibrationCurve :bins="r.reliability" :ece="r.metrics.ece.value" title="CRNN, constrained beam, real photos" />',
  }),
}

export const LetterConfusion: Story = {
  render: () => ({
    components: { ConfusionMatrix },
    setup: () => ({ c: PSEUDO.recognizers['crnn-greedy']?.letter_confusion }),
    template: '<ConfusionMatrix :confusion="c" />',
  }),
}

export const Coverage: Story = {
  render: () => ({
    components: { CoverageTable },
    setup: () => ({ single: singleViewRows(CALIBRATION), multi: fusedRows(FUSED) }),
    template: `<div style="display: grid; gap: 24px">
      <CoverageTable :rows="single" caption="One view" />
      <CoverageTable :rows="multi" caption="Fused reads" />
    </div>`,
  }),
}

export const Training: Story = {
  render: () => ({
    components: { TrainingCurve },
    setup: () => ({ t: TRAINING }),
    template:
      '<div style="max-width: 40rem"><TrainingCurve :history="t.history" :best-epoch="t.best_epoch" /></div>',
  }),
}

export const AugmentationSweep: Story = {
  render: () => ({
    components: { SweepTable },
    setup: () => ({ sweep: sweep as unknown as SweepResult }),
    template: '<SweepTable :sweep="sweep" />',
  }),
}

export const Equation: Story = {
  render: () => ({
    components: { MathBlock },
    setup: () => ({
      tex: String.raw`q_T(s \mid x) = \frac{p_T(s \mid x)}{\sum_{s' \in B_T(x)} p_T(s' \mid x)}`,
    }),
    template: '<div style="max-width: 70ch"><MathBlock :tex="tex" /></div>',
  }),
}
