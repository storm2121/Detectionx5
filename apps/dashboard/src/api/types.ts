/**
 * Response and request bodies of the plate service, mirroring services/api/schemas.py.
 * Plates come in their display spelling (`24830-ب-1`, `72173 WW`); `tokens` is the
 * canonical token string.
 */

export type Box = [number, number, number, number]

export interface Fields {
  digits: string
  letter: string | null
  region: string | null
}

export interface Candidate {
  plate: string
  tokens: string
  probability: number
}

export interface SymbolProbability {
  symbol: string
  probability: number
}

export interface PositionOut {
  index: number
  symbol: string
  confidence: number
  distribution: SymbolProbability[]
}

export interface ViewOut {
  index: number
  box: Box | null
  detector_confidence: number | null
  weight: number
  prediction: string | null
  confidence: number | null
  hypotheses: Candidate[]
  prediction_set: string[] | null
}

export type ReviewReason = 'set_size' | 'empty_set' | 'low_confidence' | 'unreadable'

export interface ReviewState {
  queued: boolean
  reason: ReviewReason | string | null
  item_id: string | null
}

export interface ReadOut {
  id: string
  created_at: string
  plate: string | null
  tokens: string | null
  format: 'standard' | 'temporary' | string | null
  fields: Fields | null
  /** Calibrated posterior of the fused read. */
  confidence: number
  calibrated: boolean
  /** Conformal set at `level`, display spellings; null when the read is not calibrated. */
  prediction_set: string[] | null
  level: number | null
  fusion: string
  model_version: string
  review: ReviewState
  views: ViewOut[]
  posterior: Candidate[]
  positions: PositionOut[]
  latency_ms: number
  status: 'accepted' | 'queued' | 'reviewed' | string
  source: string
}

export interface ReadSummary {
  id: string
  created_at: string
  plate: string | null
  confidence: number
  status: string
  source: string
  views: number
}

export interface ReadPage {
  items: ReadSummary[]
  total: number
  limit: number
  offset: number
}

export interface ReviewItemOut {
  id: string
  read_id: string
  created_at: string
  reason: string
  status: string
  plate: string | null
  confidence: number
  prediction_set: string[] | null
  corrected_plate: string | null
  /** Service paths of the crops, e.g. `/reads/<id>/views/0/crop`. */
  crops: string[]
}

export interface ReviewDecision {
  plate?: string | null
  confirm?: boolean
}

/** `GET /review/summary`: what the navigation and the export button count. */
export interface ReviewSummary {
  pending: number
  ready_to_export: number
}

export interface ExportOut {
  id: string
  exported: number
  path: string
  files: string[]
}

export type JobKind = 'folder' | 'video'

export interface JobRequest {
  kind: JobKind
  path: string
}

export interface FolderJobRead {
  image: string
  read_id?: string
  plate?: string | null
  queued?: boolean
  error?: string
}

export interface VideoTrack {
  track: number
  frames: number[]
  read_id: string
  plate: string | null
  queued: boolean
}

export interface JobResult {
  items?: number
  reads?: FolderJobRead[]
  frames?: number
  sampled?: number
  fps?: number
  tracks?: VideoTrack[]
  error?: string
}

export interface JobOut {
  id: string
  kind: JobKind | string
  source: string
  status: 'queued' | 'running' | 'finished' | 'failed' | string
  progress: number
  message: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  result: JobResult
  error: string | null
}

export interface JobProgress {
  status: string
  progress: number
  message: string
}

export interface Health {
  status: 'ok' | 'degraded' | string
  database: string
  queue: string
  model_version: string
  detector: boolean
}

export interface CRNNMetadata {
  version: string
  charset: string[]
  charset_id: string
  input: { height: number; width: number; channels: number; mean: number; std: number }
  temperature: number
  beam_width: number
  conformal: Record<string, number>
  conformal_fused?: Record<string, Record<string, number>>
  [key: string]: unknown
}

export interface RegistryModel {
  kind: string
  version: string
  file: string
  bytes?: number
  metrics?: Record<string, unknown>
  [key: string]: unknown
}

export interface Registry {
  schema?: string
  models: RegistryModel[]
  active: Record<string, string>
}

export interface ModelsOut {
  recognizer: { name: string; version: string; metadata: CRNNMetadata | null }
  detector: { available: boolean; path: string | null }
  fusion: string
  alpha: number
  review_threshold: number
  registry: Registry
}

export interface ResultEntry {
  name: string
  schema: string | null
  label: string | null
}
