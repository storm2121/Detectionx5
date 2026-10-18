/**
 * Shapes of the committed results files (results/*.json) the Evaluation, Models and Methods
 * pages render. Every number in them comes from synthetic data: synthetic results are not
 * real-world accuracy, and every page that shows one says so.
 */

export const SYNTHETIC_LABEL = 'synthetic results are not real-world accuracy'

export interface Estimate {
  value: number
  ci_low: number
  ci_high: number
  n: number
}

export interface ReliabilityBin {
  low: number
  high: number
  n: number
  accuracy: number | null
  confidence: number | null
}

export interface Confusion {
  rows: string[]
  columns: string[]
  matrix: number[][]
}

export interface Latency {
  p50: number
  p90: number
  p99: number
  mean: number
}

export interface RecognizerResult {
  n: number
  metrics: Record<string, Estimate>
  reliability: ReliabilityBin[]
  letter_confusion: Confusion
  latency_ms: Latency
  model_version: string
  calibrated: boolean
}

export interface SetInfo {
  name: string
  kind: string
  n: number
  seed: number
  generator_version: string
  source?: string
  k?: number
  n_sets?: number
}

export interface BootstrapInfo {
  resamples: number
  confidence: number
  seed: number
  unit: string
  method: string
}

export interface FusionCell {
  metrics: Record<string, Estimate>
  reliability?: ReliabilityBin[]
}

export interface FusionSection {
  set: SetInfo
  n_sets: number
  k: number[]
  bootstrap: BootstrapInfo
  recognizers: Record<
    string,
    { model_version: string; methods: Record<string, Record<string, FusionCell>> }
  >
}

export interface EvalResult {
  schema: string
  label: string
  set: SetInfo
  bootstrap: BootstrapInfo
  recognizers: Record<string, RecognizerResult>
  comparisons: Record<string, Record<string, Estimate>>
  fusion?: FusionSection
  environment: { package_version: string; device: string }
}

export interface CoverageReport {
  alpha: number
  level: number
  threshold: number
  coverage: Estimate
  set_size: Estimate
  singleton_rate: number
  empty_rate: number
  covers_everything_rate: number
  n_calibration: number
  n_test: number
  interval: string
}

export interface CalibrationSummary {
  exact_match: Estimate
  mean_confidence: Estimate
  ece: Estimate
  reliability: ReliabilityBin[]
}

export interface CalibrationResult {
  schema: string
  label: string
  model_version: string
  generator_version: string
  splits: Record<string, { seed: number; n: number }>
  bootstrap: BootstrapInfo
  temperature: {
    temperature: number
    nll_before: number
    nll_after: number
    evaluations: number
    bounds: [number, number]
  }
  calibration_split: { before: CalibrationSummary; after: CalibrationSummary }
  test_split: CalibrationSummary
  conformal: { thresholds: Record<string, number>; coverage: Record<string, CoverageReport> }
  beam_width: number
}

export interface FusedCalibrationResult {
  schema: string
  label: string
  model_version: string
  generator_version: string
  splits: Record<string, { seed: number; n_sets: number }>
  views: number[]
  fusion: string
  thresholds: Record<string, Record<string, number>>
  coverage: Record<string, Record<string, CoverageReport>>
  note: string
}

export interface TrainingEpoch {
  epoch: number
  phase: string
  loss: number
  strength_max?: number
  lr: number
  val_exact_greedy: number
  val_exact_beam?: number
  seconds: number
}

export interface TrainingResult {
  schema: string
  label: string
  generator_version: string
  train_seed: number
  val_seed: number
  config: Record<string, unknown> & { epochs: number; batch_size: number }
  device: string
  parameters: number
  seconds: number
  best_epoch: number
  best_val_exact_greedy: number
  fine_tuned_on_real_data: boolean
  history: TrainingEpoch[]
  model_version: string
}

/** Metrics where lower is better; the tables say so next to the name. */
export const LOWER_IS_BETTER = new Set(['cer', 'ece', 'set_size'])

export const METRIC_LABELS: Record<string, string> = {
  exact_match: 'Exact match',
  digits_accuracy: 'Digits',
  letter_accuracy: 'Letter',
  region_accuracy: 'Region',
  format_accuracy: 'Format',
  read_rate: 'Read rate',
  cer: 'Character error rate',
  mean_confidence: 'Mean confidence',
  ece: 'Expected calibration error',
  coverage: 'Set coverage',
  set_size: 'Mean set size',
}

/** Metrics shown as plain numbers instead of percentages. */
export const PLAIN_METRICS = new Set(['set_size'])
