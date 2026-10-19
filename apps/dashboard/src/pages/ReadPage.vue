<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api, cropUrl, errorMessage } from '@/api/client'
import type { ReadOut, ReadSummary } from '@/api/types'
import ConfidenceBar from '@/components/ConfidenceBar.vue'
import FusionTable from '@/components/FusionTable.vue'
import ModeToggle from '@/components/ModeToggle.vue'
import PhotoThumb from '@/components/PhotoThumb.vue'
import PhotoTray from '@/components/PhotoTray.vue'
import PlateReadout from '@/components/PlateReadout.vue'
import PredictionSet from '@/components/PredictionSet.vue'
import DisclosureSection from '@/components/ui/DisclosureSection.vue'
import DxButton from '@/components/ui/DxButton.vue'
import NoticeBlock from '@/components/ui/NoticeBlock.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import StatusLine from '@/components/ui/StatusLine.vue'
import SwitchField from '@/components/ui/SwitchField.vue'
import ViewCard from '@/components/ViewCard.vue'
import { dateTime, milliseconds, probability } from '@/lib/format'
import { weakestCharacter } from '@/lib/fusion'
import { fusionLabel } from '@/lib/labels'
import { reviewReason, statusLabel, statusTone, symbolLabel } from '@/lib/plate'
import { useBrowserStore } from '@/stores/browser'
import { MAX_PHOTOS, useReadStore } from '@/stores/read'
import { useServiceStore } from '@/stores/service'

const props = defineProps<{ id?: string }>()

const store = useReadStore()
const browser = useBrowserStore()
const service = useServiceStore()

const stored = shallowRef<ReadOut | null>(null)
const storedError = ref<string | null>(null)
const loadingStored = ref(false)
const recent = ref<ReadSummary[]>([])
const recentError = ref<string | null>(null)
const recentLoaded = ref(false)

const detail = computed(() => Boolean(props.id))
const read = computed(() => (detail.value ? stored.value : store.result))
const busy = computed(() => (detail.value ? loadingStored.value : store.status === 'reading'))
const errorText = computed(() => (detail.value ? storedError.value : store.error))
const threshold = computed(() => service.models?.review_threshold ?? null)
const inBrowser = computed(() => Boolean(read.value?.id.startsWith('browser-')))

/** The read's views in the order the tray shows their photos (fusion ignores the order). */
const order = computed<number[] | null>(() => {
  const value = read.value
  if (!value || detail.value) return null
  const indices = store.photos.map((p) => p.view)
  return indices.every((i): i is number => i !== null && i < value.views.length) &&
    indices.length === value.views.length
    ? indices
    : null
})
const orderedViews = computed(() => {
  const value = read.value
  if (!value) return []
  return (order.value ?? value.views.map((_, i) => i)).flatMap((i, n) => {
    const view = value.views[i]
    return view ? [{ view, number: n + 1 }] : []
  })
})
const boxes = computed(() =>
  store.photos.map((p) =>
    store.result && p.view !== null ? (store.result.views[p.view]?.box ?? null) : null,
  ),
)
const readViews = computed(() => read.value?.views.filter((v) => v.prediction !== null).length ?? 0)

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

/** Status, completion, warning and error read differently, in colour, icon and words. */
const verdict = computed(() => {
  const value = read.value
  if (!value) return null
  if (value.status === 'reviewed') return { tone: 'info' as const, label: 'Reviewed' }
  if (value.review.queued) {
    return { tone: 'warn' as const, label: `Sent to review: ${reviewReason(value.review.reason)}` }
  }
  return { tone: 'ok' as const, label: 'Accepted' }
})

const weakest = computed(() => {
  const position = read.value ? weakestCharacter(read.value.positions) : null
  return position
    ? `Least certain character: ${symbolLabel(position.symbol)} at ${probability(position.confidence, 1)}.`
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
  } finally {
    recentLoaded.value = true
  }
}

watch(
  () => store.result,
  (value) => {
    if (value) {
      void loadRecent()
      void service.refreshReview()
    }
  },
)

onMounted(() => {
  void service.loadModels()
  void loadRecent()
  if (store.mode === 'browser') void browser.prepare()
})
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>{{ detail ? 'Stored read' : 'Read a plate' }}</h1>
      <p v-if="detail">
        A read from the service's log, with the crops it kept.
        <RouterLink to="/read">Read new photos</RouterLink>
      </p>
      <p v-else>
        Add one to ten photos of the same car. Each photo is one view: the detector finds the plate,
        the recogniser reads it under the plate grammar, and the views are fused into one calibrated
        read.
      </p>
    </header>

    <div class="layout">
      <section class="inputs dx-stack" aria-labelledby="photos-title">
        <div class="dx-section-head">
          <h2 id="photos-title">{{ detail ? 'Crops' : 'Photos' }}</h2>
          <span v-if="!detail" class="dx-footnote dx-secondary">
            {{ store.photos.length }} of {{ MAX_PHOTOS }}
          </span>
        </div>

        <template v-if="!detail">
          <PhotoTray
            :photos="store.photos"
            :boxes="boxes"
            :disabled="store.status === 'reading'"
            :max-photos="MAX_PHOTOS"
            @add="store.add"
            @remove="store.remove"
            @move="store.move"
            @measure="store.measured"
          />
          <NoticeBlock
            v-if="store.rejected"
            tone="warning"
            :message="`${store.rejected} file(s) skipped: only images are read, at most ${MAX_PHOTOS} photos.`"
          />
          <div class="controls">
            <ModeToggle />
            <SwitchField
              v-model="store.detect"
              label="Find the plate in each photo"
              hint="Switch off when every photo is already a plate crop."
            />
            <div class="dx-row">
              <DxButton
                variant="primary"
                :disabled="!store.canRead"
                :busy="store.status === 'reading'"
                busy-label="Reading photos"
                data-testid="read-button"
                @click="readNow()"
              >
                Read plate
              </DxButton>
              <DxButton v-if="store.photos.length" variant="plain" @click="store.clear()">
                Remove all photos
              </DxButton>
            </div>
          </div>
        </template>

        <template v-else-if="read">
          <div class="crops">
            <template v-for="view in read.views" :key="view.index">
              <PhotoThumb
                v-if="view.prediction !== null"
                :src="cropUrl(read.id, view.index)"
                :alt="`Crop of view ${view.index + 1}`"
              >
                View {{ view.index + 1 }}
              </PhotoThumb>
            </template>
          </div>
          <p v-if="readViews === 0" class="dx-secondary">No crop was kept: no view was read.</p>
        </template>
        <SkeletonBlock v-else-if="loadingStored" kind="figure" label="Loading the crops" />
      </section>

      <section class="result dx-panel" aria-labelledby="result-title" data-testid="read-result">
        <div class="dx-section-head">
          <h2 id="result-title">Result</h2>
          <StatusLine v-if="verdict && !busy" :tone="verdict.tone" :label="verdict.label" />
        </div>
        <p class="dx-sr-only" aria-live="polite">{{ live }}</p>

        <SkeletonBlock v-if="busy" kind="plate" label="Reading the photos" />
        <NoticeBlock
          v-else-if="errorText"
          tone="error"
          title="The read failed"
          :message="`${errorText} Check that the service is running, then press Read plate again.`"
        />
        <div v-else-if="read" class="result-body">
          <PlateReadout
            :positions="read.positions"
            :fields="read.fields"
            :format="read.format"
            :plate="read.plate"
          />
          <p v-if="weakest" class="dx-footnote dx-secondary">{{ weakest }}</p>
          <ConfidenceBar
            :value="read.plate ? read.confidence : null"
            :threshold="threshold"
            :calibrated="read.calibrated"
          />
          <PredictionSet :set="read.prediction_set" :level="read.level" :prediction="read.plate" />
          <dl class="dx-facts">
            <dt>Views read</dt>
            <dd>{{ readViews }} of {{ read.views.length }}</dd>
            <dt>Fusion</dt>
            <dd>{{ fusionLabel(read.fusion) }}</dd>
            <dt>Model</dt>
            <dd>
              <code>{{ read.model_version }}</code>
            </dd>
            <dt>Time</dt>
            <dd>{{ milliseconds(read.latency_ms) }} for the whole read</dd>
            <dt>Read</dt>
            <dd v-if="inBrowser">read in this browser, not stored</dd>
            <dd v-else>
              <RouterLink :to="`/reads/${read.id}`"
                ><code>{{ read.id.slice(0, 8) }}</code></RouterLink
              >
              <span class="dx-secondary"> · {{ dateTime(read.created_at) }}</span>
            </dd>
          </dl>
        </div>
        <p v-else class="dx-secondary empty">
          The plate, its confidence and the plates that cannot be ruled out appear here. Add photos
          of one car, then press Read plate.
        </p>
      </section>
    </div>

    <section v-if="read && !busy" class="dx-section" aria-label="Views and fusion">
      <DisclosureSection
        title="Views and hypotheses"
        :summary="`${readViews} of ${read.views.length} views read · ${fusionLabel(read.fusion).toLowerCase()}`"
        :level="2"
      >
        <div class="views">
          <ViewCard
            v-for="entry in orderedViews"
            :key="entry.view.index"
            :view="entry.view"
            :number="entry.number"
            :read-id="inBrowser ? null : read.id"
            :crop-src="cropFor(entry.view.index)"
          />
        </div>
        <FusionTable :read="read" :order="order" class="fusion" />
      </DisclosureSection>
    </section>

    <section class="dx-section" aria-labelledby="recent-title">
      <div class="dx-section-head">
        <h2 id="recent-title">Recent reads</h2>
        <RouterLink to="/review" class="dx-footnote">Open the review queue</RouterLink>
      </div>
      <NoticeBlock
        v-if="recentError"
        tone="error"
        title="The read log is unavailable"
        :message="`${recentError} Reads still work; the log returns when the service does.`"
      />
      <SkeletonBlock
        v-else-if="!recentLoaded"
        kind="table"
        :rows="3"
        label="Loading recent reads"
      />
      <p v-else-if="recent.length === 0" class="dx-secondary">
        Reads the service stores appear here, newest first. Read a plate to add the first one.
      </p>
      <div v-else class="dx-scroll-x" role="region" aria-label="Recent reads" tabindex="0">
        <table class="dx-table">
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Plate</th>
              <th scope="col" class="dx-num">Confidence</th>
              <th scope="col">Status</th>
              <th scope="col" class="dx-num">Views</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in recent" :key="item.id">
              <td class="when">
                <RouterLink :to="`/reads/${item.id}`">{{ dateTime(item.created_at) }}</RouterLink>
              </td>
              <td>
                <span class="dx-plate">{{ item.plate ?? '–' }}</span>
              </td>
              <td class="dx-num">{{ probability(item.confidence, 1) }}</td>
              <td>
                <StatusLine :tone="statusTone(item.status)" :label="statusLabel(item.status)" />
              </td>
              <td class="dx-num">{{ item.views }} {{ item.views === 1 ? 'view' : 'views' }}</td>
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
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--dx-space-6);
  align-items: start;
}

.controls {
  display: grid;
  gap: var(--dx-space-4);
  padding-top: var(--dx-space-2);
}

.result {
  display: grid;
  gap: var(--dx-space-4);
  position: sticky;
  top: calc(var(--dx-bar-height) + var(--dx-space-4));
}

.result-body {
  display: grid;
  gap: var(--dx-space-5);
  min-width: 0;
}

.empty {
  max-width: var(--dx-measure);
}

.crops {
  display: grid;
  gap: var(--dx-space-3);
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 10rem), 1fr));
}

.views {
  display: grid;
  gap: var(--dx-space-4);
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 17rem), 1fr));
}

.fusion {
  margin-top: var(--dx-space-5);
}

.when {
  white-space: nowrap;
}

@media (max-width: 960px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .result {
    position: static;
  }
}
</style>
