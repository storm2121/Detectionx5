<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api, errorMessage, jobEventsUrl } from '@/api/client'
import type { JobKind, JobOut, JobProgress } from '@/api/types'
import ProgressBar from '@/components/ProgressBar.vue'
import DxButton from '@/components/ui/DxButton.vue'
import NoticeBlock from '@/components/ui/NoticeBlock.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import StatusLine from '@/components/ui/StatusLine.vue'
import TextField from '@/components/ui/TextField.vue'
import { dateTime, percent } from '@/lib/format'
import { jobRate, rateText } from '@/lib/jobs'
import { statusLabel, statusTone } from '@/lib/plate'

const jobs = ref<JobOut[]>([])
const loading = ref(true)
const listError = ref<string | null>(null)
const selected = ref<JobOut | null>(null)
const now = ref(Date.now())

const kind = ref<JobKind>('folder')
const path = ref('')
const pathTouched = ref(false)
const submitting = ref(false)
const formError = ref<string | null>(null)
const video = ref<File | null>(null)
const uploadError = ref<string | null>(null)
const uploading = ref(false)

const kinds = [
  { label: 'Folder of photos', value: 'folder' as const },
  { label: 'Video', value: 'video' as const },
]

let source: EventSource | null = null
let poll: number | undefined
let clock: number | undefined

const active = computed(() =>
  jobs.value.some((j) => j.status === 'queued' || j.status === 'running'),
)
const pathError = computed(() => {
  if (formError.value) return formError.value
  if (pathTouched.value && !path.value.trim()) {
    return 'Give a path under the jobs root, for example batch-01.'
  }
  return null
})

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
    jobs.value = jobs.value.map((j) => (j.id === job.id ? { ...j, ...update } : j))
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
  pathTouched.value = true
  if (!path.value.trim()) return
  submitting.value = true
  try {
    const job = await api.createJob({ kind: kind.value, path: path.value.trim() })
    await refresh()
    follow(job)
  } catch (cause) {
    formError.value = `${errorMessage(cause)} Check the path, then queue it again.`
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
  if (!video.value) return
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
  clock = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  stopFollowing()
  window.clearInterval(poll)
  window.clearInterval(clock)
})
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>Jobs</h1>
      <p>
        Background reads run on the worker: a folder of photos (one read per photo) or a video
        (plates are tracked across frames and each track's frames are fused into one read). Progress
        streams live from the service.
      </p>
    </header>

    <div class="forms">
      <section class="dx-section" aria-labelledby="new-title">
        <h2 id="new-title">Queue a folder or a video</h2>
        <form class="form" novalidate @submit.prevent="submit">
          <SegmentedControl v-model="kind" :options="kinds" label="Kind of job" />
          <TextField
            id="job-path"
            v-model="path"
            label="Path under the jobs root"
            :placeholder="kind === 'folder' ? 'batch-01' : 'camera-2/morning.mp4'"
            hint="Relative to PLATE_JOBS_ROOT on the service; nothing outside it is read."
            :error="pathError"
            @blur="pathTouched = true"
            @update:model-value="formError = null"
          />
          <div>
            <DxButton
              type="submit"
              variant="primary"
              :busy="submitting"
              busy-label="Queueing"
              data-testid="queue-job"
            >
              Queue job
            </DxButton>
          </div>
        </form>
      </section>

      <section class="dx-section" aria-labelledby="upload-title">
        <h2 id="upload-title">Upload a video</h2>
        <div class="form">
          <div class="file-field">
            <label for="job-video" class="dx-label">Video file</label>
            <input
              id="job-video"
              class="file"
              type="file"
              accept="video/mp4,video/x-msvideo,video/quicktime,video/x-matroska,.mp4,.avi,.mov,.mkv"
              @change="pickVideo"
            />
            <p class="dx-footnote dx-secondary">The service samples a frame every half second.</p>
          </div>
          <NoticeBlock
            v-if="uploadError"
            tone="error"
            title="The video was not queued"
            :message="`${uploadError} Choose an mp4, avi, mov or mkv file and upload it again.`"
          />
          <div>
            <DxButton :disabled="!video" :busy="uploading" busy-label="Uploading" @click="upload">
              Upload and queue
            </DxButton>
          </div>
        </div>
      </section>
    </div>

    <section
      v-if="selected"
      class="dx-section"
      aria-labelledby="job-title"
      data-testid="job-detail"
    >
      <div class="dx-section-head">
        <h2 id="job-title">Job {{ selected.id.slice(0, 8) }}</h2>
        <StatusLine :tone="statusTone(selected.status)" :label="statusLabel(selected.status)" />
      </div>
      <ProgressBar :value="selected.progress" label="Job progress" />
      <p class="dx-footnote dx-secondary" aria-live="polite">
        {{ percent(selected.progress, 0) }} done<template v-if="rateText(jobRate(selected, now))">
          · {{ rateText(jobRate(selected, now)) }}</template
        ><template v-else> · {{ selected.message }}</template>
      </p>
      <NoticeBlock
        v-if="selected.error"
        tone="error"
        title="The job failed"
        :message="`${selected.error} Fix the source, then queue it again.`"
      />

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
            photos, one read each
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
                  <span class="dx-plate">{{ item.plate ?? 'no plate' }}</span>
                </RouterLink>
                <span v-else class="dx-secondary">{{ item.error }}</span>
              </td>
              <td>{{ item.queued ? 'waiting for review' : '–' }}</td>
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
            frames,
            {{
              selected.result.sampled
            }}
            of them sampled
          </caption>
          <thead>
            <tr>
              <th scope="col">Track</th>
              <th scope="col" class="dx-num">Frames</th>
              <th scope="col">Plate</th>
              <th scope="col">Review</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="track in selected.result.tracks" :key="track.track">
              <td>{{ track.track }}</td>
              <td class="dx-num">{{ track.frames.length }} frames</td>
              <td>
                <RouterLink :to="`/reads/${track.read_id}`">
                  <span class="dx-plate">{{ track.plate ?? 'no plate' }}</span>
                </RouterLink>
              </td>
              <td>{{ track.queued ? 'waiting for review' : '–' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="dx-section" aria-labelledby="list-title">
      <div class="dx-section-head">
        <h2 id="list-title">Recent jobs</h2>
        <DxButton variant="plain" size="small" @click="refresh">Check for updates</DxButton>
      </div>
      <SkeletonBlock v-if="loading" kind="table" :rows="3" label="Loading jobs" />
      <NoticeBlock
        v-else-if="listError"
        tone="error"
        title="Jobs are unavailable"
        :message="`${listError} Queued jobs keep running on the worker.`"
      />
      <p v-else-if="jobs.length === 0" class="dx-secondary">
        Folders and videos queued above appear here with their progress. Queue one to start.
      </p>
      <div v-else class="dx-scroll-x" role="region" aria-label="Recent jobs" tabindex="0">
        <table class="dx-table" data-testid="jobs-table">
          <thead>
            <tr>
              <th scope="col">Created</th>
              <th scope="col">Kind</th>
              <th scope="col">Source</th>
              <th scope="col">Status</th>
              <th scope="col">Progress</th>
              <th scope="col"><span class="dx-sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id" :class="{ current: selected?.id === job.id }">
              <td class="nowrap">{{ dateTime(job.created_at) }}</td>
              <td>{{ job.kind }}</td>
              <td class="source">{{ job.source }}</td>
              <td>
                <StatusLine :tone="statusTone(job.status)" :label="statusLabel(job.status)" />
              </td>
              <td>
                <span class="progress-cell">
                  <ProgressBar
                    :value="job.progress"
                    :label="`Progress of job ${job.id.slice(0, 8)}`"
                    size="small"
                  />
                  <span class="nowrap">{{ percent(job.progress, 0) }}</span>
                </span>
              </td>
              <td>
                <DxButton
                  variant="plain"
                  size="small"
                  :aria-label="`Open job ${job.id.slice(0, 8)}`"
                  @click="follow(job)"
                >
                  Open
                </DxButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.forms {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
  gap: var(--dx-space-6);
  align-items: start;
}

.form {
  display: grid;
  gap: var(--dx-space-4);
}

.file-field {
  display: grid;
  gap: var(--dx-space-1);
}

.file {
  max-width: 100%;
  color: var(--dx-text-2);
  font-size: var(--dx-text-dense);
}

/* the platform's file picker, dressed as the console's secondary button */
.file::file-selector-button {
  min-height: var(--dx-target);
  margin-right: var(--dx-space-3);
  padding: 0 var(--dx-space-4);
  border: var(--dx-line) solid var(--dx-border-strong);
  border-radius: var(--dx-radius-control);
  background: var(--dx-surface);
  color: var(--dx-text);
  font: inherit;
  font-weight: var(--dx-weight-label);
  cursor: pointer;
}

.file::file-selector-button:hover {
  background: var(--dx-surface-inset);
}

.progress-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--dx-space-2);
}

.source {
  max-width: 18rem;
  overflow-wrap: anywhere;
}

.nowrap {
  white-space: nowrap;
}

tr.current > * {
  background: var(--dx-accent-soft);
}
</style>
