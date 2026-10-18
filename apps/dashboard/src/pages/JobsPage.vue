<script setup lang="ts">
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import SelectButton from 'primevue/selectbutton'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api, errorMessage, jobEventsUrl } from '@/api/client'
import type { JobKind, JobOut, JobProgress } from '@/api/types'
import ErrorNote from '@/components/ErrorNote.vue'
import LoadingState from '@/components/LoadingState.vue'
import StatusPill from '@/components/StatusPill.vue'
import { dateTime, percent } from '@/lib/format'
import { statusTone } from '@/lib/plate'

const jobs = ref<JobOut[]>([])
const loading = ref(true)
const listError = ref<string | null>(null)
const selected = ref<JobOut | null>(null)

const kind = ref<JobKind>('folder')
const path = ref('')
const submitting = ref(false)
const formError = ref<string | null>(null)
const video = ref<File | null>(null)
const uploadError = ref<string | null>(null)
const uploading = ref(false)

const kinds = [
  { label: 'Folder of photos', value: 'folder' },
  { label: 'Video', value: 'video' },
]

let source: EventSource | null = null
let poll: number | undefined

const active = computed(() =>
  jobs.value.some((j) => j.status === 'queued' || j.status === 'running'),
)

async function refresh() {
  try {
    jobs.value = await api.jobs(25)
    listError.value = null
    if (selected.value) {
      const fresh = jobs.value.find((j) => j.id === selected.value?.id)
      if (fresh && !source) selected.value = fresh
    }
  } catch (cause) {
    listError.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}

function stopFollowing() {
  source?.close()
  source = null
}

function follow(job: JobOut) {
  stopFollowing()
  selected.value = job
  if (job.status === 'finished' || job.status === 'failed' || typeof EventSource === 'undefined') {
    return
  }
  const events = new EventSource(jobEventsUrl(job.id))
  source = events
  events.addEventListener('progress', (event) => {
    const update = JSON.parse((event as MessageEvent<string>).data) as JobProgress
    if (selected.value?.id === job.id) selected.value = { ...selected.value, ...update }
  })
  events.addEventListener('done', (event) => {
    const done = JSON.parse((event as MessageEvent<string>).data) as JobOut
    if (selected.value?.id === job.id) selected.value = done
    stopFollowing()
    void refresh()
  })
  events.onerror = () => {
    stopFollowing()
    void refresh()
  }
}

async function submit() {
  formError.value = null
  if (!path.value.trim()) {
    formError.value = 'Give a path under the jobs root, for example batch-01.'
    return
  }
  submitting.value = true
  try {
    const job = await api.createJob({ kind: kind.value, path: path.value.trim() })
    await refresh()
    follow(job)
  } catch (cause) {
    formError.value = errorMessage(cause)
  } finally {
    submitting.value = false
  }
}

function pickVideo(event: Event) {
  const files = (event.target as HTMLInputElement).files
  video.value = files && files.length > 0 ? (files[0] ?? null) : null
  uploadError.value = null
}

async function upload() {
  if (!video.value) {
    uploadError.value = 'Choose a video first.'
    return
  }
  uploading.value = true
  uploadError.value = null
  try {
    const job = await api.uploadJob(video.value)
    await refresh()
    follow(job)
  } catch (cause) {
    uploadError.value = errorMessage(cause)
  } finally {
    uploading.value = false
  }
}

onMounted(() => {
  void refresh()
  poll = window.setInterval(() => {
    if (active.value && !source) void refresh()
  }, 3000)
})

onBeforeUnmount(() => {
  stopFollowing()
  window.clearInterval(poll)
})
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>Jobs</h1>
      <p class="dx-lead">
        Background reads run on the worker: a folder of photos (one read per photo) or a video
        (plates are tracked across frames and every track's best frames are fused into one read).
        Progress streams live from the service.
      </p>
    </header>

    <div class="dx-grid-2">
      <section class="dx-card" aria-labelledby="new-title">
        <h2 id="new-title" class="card-title">Queue a folder or a video</h2>
        <form class="form" novalidate @submit.prevent="submit">
          <fieldset class="field">
            <legend>Kind</legend>
            <SelectButton
              v-model="kind"
              :options="kinds"
              option-label="label"
              option-value="value"
              :allow-empty="false"
              aria-label="Kind of job"
            />
          </fieldset>
          <div class="field">
            <label for="job-path">Path under the jobs root</label>
            <InputText
              id="job-path"
              v-model="path"
              :placeholder="kind === 'folder' ? 'batch-01' : 'camera-2/morning.mp4'"
              autocomplete="off"
              :invalid="Boolean(formError)"
              aria-describedby="job-path-help"
            />
            <small id="job-path-help" class="dx-muted">
              Relative to <code>PLATE_JOBS_ROOT</code> on the service; nothing outside it is read.
            </small>
          </div>
          <ErrorNote v-if="formError" :message="formError" title="The job was not queued" />
          <div>
            <Button type="submit" label="Queue job" :loading="submitting" data-testid="queue-job" />
          </div>
        </form>
      </section>

      <section class="dx-card" aria-labelledby="upload-title">
        <h2 id="upload-title" class="card-title">Upload a video</h2>
        <div class="form">
          <div class="field">
            <label for="job-video">Video file</label>
            <input
              id="job-video"
              class="file"
              type="file"
              accept="video/mp4,video/x-msvideo,video/quicktime,video/x-matroska,.mp4,.avi,.mov,.mkv"
              @change="pickVideo"
            />
            <small class="dx-muted"
              >The service samples a frame every half second by default.</small
            >
          </div>
          <ErrorNote v-if="uploadError" :message="uploadError" title="The video was not queued" />
          <div>
            <Button
              label="Upload and queue"
              severity="secondary"
              :loading="uploading"
              :disabled="!video"
              @click="upload"
            />
          </div>
        </div>
      </section>
    </div>

    <section v-if="selected" class="dx-card" aria-labelledby="job-title" data-testid="job-detail">
      <div class="dx-card-head">
        <h2 id="job-title">Job {{ selected.id.slice(0, 8) }}</h2>
        <StatusPill :tone="statusTone(selected.status)" :label="selected.status" />
      </div>
      <div
        class="progress"
        role="progressbar"
        aria-label="Job progress"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-valuenow="Math.round(selected.progress * 100)"
      >
        <div class="progress-fill" :style="{ transform: `scaleX(${selected.progress})` }" />
      </div>
      <p class="dx-small dx-muted" aria-live="polite">
        {{ percent(selected.progress, 0) }} · {{ selected.message }}
      </p>
      <ErrorNote v-if="selected.error" :message="selected.error" title="The job failed" />

      <div
        v-if="selected.result.reads?.length"
        class="dx-scroll-x"
        role="region"
        aria-label="Job reads"
        tabindex="0"
      >
        <table class="dx-table">
          <caption>
            {{
              selected.result.items
            }}
            photos
          </caption>
          <thead>
            <tr>
              <th scope="col">Photo</th>
              <th scope="col">Plate</th>
              <th scope="col">Review</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in selected.result.reads" :key="item.image">
              <td>{{ item.image }}</td>
              <td>
                <RouterLink v-if="item.read_id" :to="`/reads/${item.read_id}`">
                  <span class="dx-plate-text">{{ item.plate ?? 'no plate' }}</span>
                </RouterLink>
                <span v-else class="dx-muted">{{ item.error }}</span>
              </td>
              <td>{{ item.queued ? 'queued' : '' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        v-if="selected.result.tracks?.length"
        class="dx-scroll-x"
        role="region"
        aria-label="Job tracks"
        tabindex="0"
      >
        <table class="dx-table">
          <caption>
            {{
              selected.result.tracks.length
            }}
            tracks over
            {{
              selected.result.frames
            }}
            frames ({{
              selected.result.sampled
            }}
            sampled)
          </caption>
          <thead>
            <tr>
              <th scope="col">Track</th>
              <th scope="col" class="dx-right">Frames</th>
              <th scope="col">Plate</th>
              <th scope="col">Review</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="track in selected.result.tracks" :key="track.track">
              <td class="dx-num">{{ track.track }}</td>
              <td class="dx-right dx-num">{{ track.frames.length }}</td>
              <td>
                <RouterLink :to="`/reads/${track.read_id}`">
                  <span class="dx-plate-text">{{ track.plate ?? 'no plate' }}</span>
                </RouterLink>
              </td>
              <td>{{ track.queued ? 'queued' : '' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="dx-card" aria-labelledby="list-title">
      <div class="dx-card-head">
        <h2 id="list-title">Recent jobs</h2>
        <Button label="Refresh" severity="secondary" text size="small" @click="refresh" />
      </div>
      <LoadingState v-if="loading" label="Loading jobs" />
      <ErrorNote v-else-if="listError" :message="listError" title="Jobs are unavailable" />
      <p v-else-if="jobs.length === 0" class="dx-muted">No jobs yet.</p>
      <div v-else class="dx-scroll-x" role="region" aria-label="Recent jobs" tabindex="0">
        <table class="dx-table" data-testid="jobs-table">
          <thead>
            <tr>
              <th scope="col">Created</th>
              <th scope="col">Kind</th>
              <th scope="col">Source</th>
              <th scope="col">Status</th>
              <th scope="col" class="dx-right">Progress</th>
              <th scope="col"><span class="dx-sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id" :class="{ current: selected?.id === job.id }">
              <td>{{ dateTime(job.created_at) }}</td>
              <td>{{ job.kind }}</td>
              <td class="source">{{ job.source }}</td>
              <td><StatusPill :tone="statusTone(job.status)" :label="job.status" /></td>
              <td class="dx-right dx-num">{{ percent(job.progress, 0) }}</td>
              <td>
                <Button
                  label="Open"
                  size="small"
                  severity="secondary"
                  text
                  :aria-label="`Open job ${job.id.slice(0, 8)}`"
                  @click="follow(job)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.card-title {
  margin-bottom: var(--dx-space-3);
}

.form {
  display: grid;
  gap: var(--dx-space-3);
}

.field {
  display: grid;
  gap: var(--dx-space-1);
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}

.field label,
.field legend {
  font-weight: 600;
  font-size: var(--dx-text-sm);
  padding: 0;
  margin-bottom: var(--dx-space-1);
}

.file {
  font: inherit;
  max-width: 100%;
}

.progress {
  height: 10px;
  border-radius: 999px;
  background: var(--dx-surface-sunken);
  border: 1px solid var(--dx-border);
  overflow: hidden;
  margin-bottom: var(--dx-space-2);
}

.progress-fill {
  height: 100%;
  background: var(--dx-accent);
  transform-origin: left center;
  transition: transform 240ms ease;
}

.source {
  max-width: 280px;
  overflow-wrap: anywhere;
}

tr.current td {
  background: var(--dx-accent-soft);
}
</style>
