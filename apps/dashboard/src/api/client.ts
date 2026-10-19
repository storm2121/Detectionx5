import type {
  ExportOut,
  Health,
  JobOut,
  JobRequest,
  ModelsOut,
  ReadOut,
  ReadPage,
  ResultEntry,
  ReviewDecision,
  ReviewItemOut,
  ReviewSummary,
} from './types'

/** Every call goes to `/api/...`; Vite's dev server and nginx forward it to the service. */
export const API_BASE = (import.meta.env.VITE_API_BASE ?? '/api').replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** The service's own explanation when it gives one (FastAPI `detail`), else the status. */
export function describeError(status: number, body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first: unknown = detail[0]
      if (first && typeof first === 'object' && 'msg' in first) {
        return String((first as { msg: unknown }).msg).replace(/^Value error, /, '')
      }
    }
  }
  if (status === 0) return 'The plate service cannot be reached.'
  return `The plate service answered with status ${status}.`
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return String(error)
}

type Fetch = typeof fetch

let fetcher: Fetch = (...args) => fetch(...args)

/** Tests and stories swap the transport; the app never does. */
export function setFetch(next: Fetch | null): void {
  fetcher = next ?? ((...args) => fetch(...args))
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  let response: Response
  try {
    response = await fetcher(`${API_BASE}${path}`, { ...init, headers })
  } catch (cause) {
    throw new ApiError(0, describeError(0, null), cause)
  }
  if (!response.ok) {
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      body = null
    }
    throw new ApiError(response.status, describeError(response.status, body), body)
  }
  return (await response.json()) as T
}

function json(body: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  health: () => request<Health>('/health'),
  models: () => request<ModelsOut>('/models'),

  read(files: readonly File[], detect = true): Promise<ReadOut> {
    const body = new FormData()
    files.forEach((file) => body.append('files', file, file.name))
    return request<ReadOut>(`/read${query({ detect })}`, { method: 'POST', body })
  },
  reads: (params: { status?: string; limit?: number; offset?: number } = {}) =>
    request<ReadPage>(`/reads${query(params)}`),
  readById: (id: string) => request<ReadOut>(`/reads/${encodeURIComponent(id)}`),

  reviewQueue: (limit = 50) => request<ReviewItemOut[]>(`/review/queue${query({ limit })}`),
  decide: (itemId: string, decision: ReviewDecision) =>
    request<ReviewItemOut>(`/review/${encodeURIComponent(itemId)}`, json(decision)),
  reviewSummary: () => request<ReviewSummary>('/review/summary'),
  exportReviewed: () => request<ExportOut>('/review/export', { method: 'POST' }),

  jobs: (limit = 20) => request<JobOut[]>(`/jobs${query({ limit })}`),
  job: (id: string) => request<JobOut>(`/jobs/${encodeURIComponent(id)}`),
  createJob: (body: JobRequest) => request<JobOut>('/jobs', json(body)),
  uploadJob(video: File): Promise<JobOut> {
    const body = new FormData()
    body.append('video', video, video.name)
    return request<JobOut>('/jobs/upload', { method: 'POST', body })
  },

  results: () => request<ResultEntry[]>('/results'),
  result: <T>(name: string) => request<T>(`/results/${encodeURIComponent(name)}`),
}

/** URL of a service path for image elements and EventSource (crops, job events). */
export function serviceUrl(path: string): string {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

export function cropUrl(readId: string, index: number): string {
  return serviceUrl(`/reads/${encodeURIComponent(readId)}/views/${index}/crop`)
}

export function jobEventsUrl(jobId: string): string {
  return serviceUrl(`/jobs/${encodeURIComponent(jobId)}/events`)
}
