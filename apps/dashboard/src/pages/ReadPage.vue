<script setup lang="ts">
import Button from 'primevue/button'
import ToggleSwitch from 'primevue/toggleswitch'
import { computed, onMounted, ref, shallowRef, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api, cropUrl, errorMessage } from '@/api/client'
import type { ReadOut, ReadSummary } from '@/api/types'
import CharacterHeatmap from '@/components/CharacterHeatmap.vue'
import ConfidenceMeter from '@/components/ConfidenceMeter.vue'
import ConformalSet from '@/components/ConformalSet.vue'
import ErrorNote from '@/components/ErrorNote.vue'
import FusionTable from '@/components/FusionTable.vue'
import LoadingState from '@/components/LoadingState.vue'
import ModeToggle from '@/components/ModeToggle.vue'
import PhotoDrop from '@/components/PhotoDrop.vue'
import PhotoFrame from '@/components/PhotoFrame.vue'
import PlateFields from '@/components/PlateFields.vue'
import StatusPill from '@/components/StatusPill.vue'
import SyntheticNote from '@/components/SyntheticNote.vue'
import ViewCard from '@/components/ViewCard.vue'
import { dateTime, milliseconds, probability } from '@/lib/format'
import { weakestCharacter } from '@/lib/fusion'
import { fusionLabel } from '@/lib/labels'
import { reviewReason, statusTone, symbolLabel } from '@/lib/plate'
import { useBrowserStore } from '@/stores/browser'
import { MAX_PHOTOS, useReadStore } from '@/stores/read'
import { useServiceStore } from '@/stores/service'

const props = defineProps<{ id?: string }>()

const store = useReadStore()
const browser = useBrowserStore()
const service = useServiceStore()

const SAMPLES = ['scene_00.png', 'scene_01.png', 'scene_02.png']

const stored = shallowRef<ReadOut | null>(null)
const storedError = ref<string | null>(null)
const loadingStored = ref(false)
const recent = ref<ReadSummary[]>([])
const recentError = ref<string | null>(null)

const detail = computed(() => Boolean(props.id))
const read = computed(() => (detail.value ? stored.value : store.result))
const busy = computed(() => (detail.value ? loadingStored.value : store.status === 'reading'))
const errorText = computed(() => (detail.value ? storedError.value : store.error))
const threshold = computed(() => service.models?.review_threshold ?? null)
const inBrowser = computed(() => Boolean(read.value?.id.startsWith('browser-')))

function readNow() {
  void store.read({
    alpha: service.models?.alpha ?? 0.05,
    reviewThreshold: service.models?.review_threshold ?? 0.9,
    backend: browser.backend ?? 'wasm',
  })
}

function cropFor(index: number): string | null {
  return inBrowser.value ? (store.browserCrops[index] ?? null) : null
}
const readViews = computed(() => read.value?.views.filter((v) => v.prediction !== null).length ?? 0)

const verdict = computed(() => {
  const value = read.value
  if (!value) return null
  if (value.status === 'reviewed') return { tone: 'info' as const, label: 'reviewed' }
  if (value.review.queued) {
    return { tone: 'warn' as const, label: `review: ${reviewReason(value.review.reason)}` }
  }
  return { tone: 'ok' as const, label: 'accepted' }
})

const weakest = computed(() => {
  const position = read.value ? weakestCharacter(read.value.positions) : null
  return position
    ? `Least certain character: ${symbolLabel(position.symbol)} at ${probability(position.confidence, 1)}`
    : ''
})

const live = computed(() => {
  if (busy.value) return 'Reading the photos.'
  if (errorText.value) return `The read failed: ${errorText.value}`
  const value = read.value
  if (!value) return ''
  return value.plate
    ? `Read ${value.plate} at ${probability(value.confidence, 1)} confidence; ${verdict.value?.label}.`
    : 'No plate was read.'
})

watch(
  () => props.id,
  async (id) => {
    if (!id) return
    loadingStored.value = true
    storedError.value = null
    try {
      stored.value = await api.readById(id)
    } catch (cause) {
      stored.value = null
      storedError.value = errorMessage(cause)
    } finally {
      loadingStored.value = false
    }
  },
  { immediate: true },
)

async function loadRecent() {
  try {
    recent.value = (await api.reads({ limit: 8 })).items
    recentError.value = null
  } catch (cause) {
    recentError.value = errorMessage(cause)
  }
}

watch(
  () => store.result,
  (value) => {
    if (value) void loadRecent()
  },
)

onMounted(() => {
  void service.loadModels()
  void loadRecent()
  if (store.mode === 'browser') void browser.prepare()
})

async function trySamples() {
  try {
    await store.loadSamples(SAMPLES)
  } catch (cause) {
    store.error = errorMessage(cause)
    store.status = 'error'
  }
}

function boxFor(index: number) {
  return store.result?.views[index]?.box ?? null
}
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>{{ detail ? 'Stored read' : 'Read a plate' }}</h1>
      <p class="dx-lead">
        <template v-if="detail">
          A read from the service's log, with the crops it kept for review.
          <RouterLink to="/read">Read new photos</RouterLink>.
        </template>
        <template v-else>
          Drop one to ten photos of the same car. Each photo is one view: the detector finds the
          plate, the recogniser reads it with the plate grammar, and the views are fused into one
          calibrated read with a conformal prediction set.
        </template>
      </p>
    </header>

    <div class="layout">
      <section class="dx-card inputs" aria-labelledby="photos-title">
        <div class="dx-card-head">
          <h2 id="photos-title">{{ detail ? 'Crops' : 'Photos' }}</h2>
          <span v-if="!detail" class="dx-small dx-muted dx-num">
            {{ store.photos.length }} of {{ MAX_PHOTOS }}
          </span>
        </div>

        <template v-if="!detail">
          <PhotoDrop
            :disabled="store.status === 'reading'"
            :max-photos="MAX_PHOTOS"
            @add="store.add"
          />
          <p v-if="store.rejected" class="dx-small skipped">
            {{ store.rejected }} file(s) skipped: not an image, or more than
            {{ MAX_PHOTOS }} photos.
          </p>
          <div v-if="store.photos.length" class="photos" data-testid="photos">
            <PhotoFrame
              v-for="(photo, index) in store.photos"
              :key="photo.id"
              :src="photo.url"
              :alt="`Photo ${index + 1}, ${photo.file.name}`"
              :box="boxFor(index)"
              :badge="`View ${index + 1}`"
              removable
              @remove="store.remove(photo.id)"
              @measure="(w: number, h: number) => store.measured(photo.id, w, h)"
            >
              {{ photo.file.name }}
            </PhotoFrame>
          </div>
          <div class="controls">
            <ModeToggle />
            <div class="switch">
              <ToggleSwitch v-model="store.detect" input-id="detect-plates" />
              <label for="detect-plates">Find the plate in each photo</label>
            </div>
            <p class="dx-small dx-muted">Switch off when every photo is already a plate crop.</p>
            <div class="dx-row">
              <Button
                label="Read plate"
                :loading="store.status === 'reading'"
                :disabled="!store.canRead"
                data-testid="read-button"
                @click="readNow()"
              />
              <Button
                label="Try three synthetic photos"
                severity="secondary"
                outlined
                data-testid="samples-button"
                @click="trySamples()"
              />
              <Button
                v-if="store.photos.length"
                label="Clear"
                severity="secondary"
                text
                @click="store.clear()"
              />
            </div>
          </div>
        </template>

        <template v-else-if="read">
          <div class="photos">
            <template v-for="view in read.views" :key="view.index">
              <PhotoFrame
                v-if="view.prediction !== null"
                :src="cropUrl(read.id, view.index)"
                :alt="`Crop of view ${view.index + 1}`"
                :badge="`View ${view.index + 1}`"
              />
            </template>
          </div>
          <p v-if="readViews === 0" class="dx-muted">No crop was kept: no view was read.</p>
        </template>
      </section>

      <section class="dx-card result" aria-labelledby="result-title" data-testid="read-result">
        <div class="dx-card-head">
          <h2 id="result-title">Result</h2>
          <StatusPill v-if="verdict && !busy" :tone="verdict.tone" :label="verdict.label" />
        </div>
        <p class="dx-sr-only" aria-live="polite">{{ live }}</p>

        <LoadingState v-if="busy" label="Reading" />
        <ErrorNote v-else-if="errorText" :message="errorText" title="The read failed" />
        <div v-else-if="read" class="dx-stack result-body">
          <PlateFields :fields="read.fields" :format="read.format" :plate="read.plate" />
          <ConfidenceMeter
            :value="read.plate ? read.confidence : null"
            :threshold="threshold"
            :calibrated="read.calibrated"
            label="Calibrated confidence"
          />
          <ConformalSet :set="read.prediction_set" :level="read.level" :prediction="read.plate" />
          <dl class="dx-dl">
            <dt>Views read</dt>
            <dd class="dx-num">{{ readViews }} of {{ read.views.length }}</dd>
            <dt>Fusion</dt>
            <dd>{{ fusionLabel(read.fusion) }}</dd>
            <dt>Model</dt>
            <dd>
              <code>{{ read.model_version }}</code>
            </dd>
            <dt>Latency</dt>
            <dd class="dx-num">{{ milliseconds(read.latency_ms) }}</dd>
            <dt>Read</dt>
            <dd v-if="inBrowser">read in this browser, not stored</dd>
            <dd v-else>
              <RouterLink :to="`/reads/${read.id}`"
                ><code>{{ read.id.slice(0, 8) }}</code></RouterLink
              >
              <span class="dx-muted dx-ci">· {{ dateTime(read.created_at) }}</span>
            </dd>
          </dl>
          <SyntheticNote
            detail="The recogniser was trained and calibrated on synthetic plates, so this confidence and this set describe synthetic data."
          />
        </div>
        <p v-else class="dx-muted">
          Add photos, or try three synthetic photos of one car, then press Read plate.
        </p>
      </section>
    </div>

    <template v-if="read && !busy">
      <section class="dx-stack" aria-labelledby="views-title">
        <div class="section-head">
          <h2 id="views-title">Views</h2>
          <p class="dx-muted dx-small">
            Each photo's best detection, read by the constrained beam; highlighted hypotheses are in
            that view's own conformal set.
          </p>
        </div>
        <div class="dx-grid-3">
          <ViewCard
            v-for="view in read.views"
            :key="view.index"
            :view="view"
            :read-id="inBrowser ? null : read.id"
            :crop-src="cropFor(view.index)"
          />
        </div>
      </section>

      <section class="dx-card" aria-labelledby="fusion-title">
        <div class="dx-card-head">
          <h2 id="fusion-title">Fusion</h2>
          <span class="dx-small dx-muted">{{ fusionLabel(read.fusion) }}</span>
        </div>
        <FusionTable :read="read" />
      </section>

      <section class="dx-card" aria-labelledby="chars-title">
        <div class="dx-card-head">
          <h2 id="chars-title">Characters</h2>
          <span class="dx-small dx-muted">{{ weakest }}</span>
        </div>
        <CharacterHeatmap v-if="read.positions.length" :positions="read.positions" />
        <p v-else class="dx-muted">Nothing was read, so there are no characters to show.</p>
      </section>
    </template>

    <section class="dx-card" aria-labelledby="recent-title">
      <div class="dx-card-head">
        <h2 id="recent-title">Recent reads</h2>
        <RouterLink to="/review" class="dx-small">Review queue</RouterLink>
      </div>
      <ErrorNote v-if="recentError" :message="recentError" title="The read log is unavailable" />
      <p v-else-if="recent.length === 0" class="dx-muted">No reads yet.</p>
      <div v-else class="dx-scroll-x" role="region" aria-label="Recent reads" tabindex="0">
        <table class="dx-table">
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Plate</th>
              <th scope="col" class="dx-right">Confidence</th>
              <th scope="col">Status</th>
              <th scope="col" class="dx-right">Views</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in recent" :key="item.id">
              <td class="when">
                <RouterLink :to="`/reads/${item.id}`">{{ dateTime(item.created_at) }}</RouterLink>
              </td>
              <td>
                <span class="dx-plate-text">{{ item.plate ?? '–' }}</span>
              </td>
              <td class="dx-right dx-num">{{ probability(item.confidence, 1) }}</td>
              <td><StatusPill :tone="statusTone(item.status)" :label="item.status" /></td>
              <td class="dx-right dx-num">{{ item.views }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  gap: var(--dx-space-4);
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  align-items: start;
}

.inputs,
.result {
  display: grid;
  gap: var(--dx-space-3);
}

.result-body {
  gap: var(--dx-space-4);
}

.photos {
  display: grid;
  gap: var(--dx-space-3);
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 140px), 1fr));
}

.when {
  white-space: nowrap;
}

.controls {
  display: grid;
  gap: var(--dx-space-2);
}

.switch {
  display: flex;
  align-items: center;
  gap: var(--dx-space-2);
  font-weight: 550;
}

.skipped {
  color: var(--dx-warn);
}

.section-head {
  display: grid;
  gap: var(--dx-space-1);
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
