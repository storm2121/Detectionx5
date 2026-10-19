<script setup lang="ts">
import { Download } from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api, errorMessage, serviceUrl } from '@/api/client'
import type { ExportOut, ReviewItemOut } from '@/api/types'
import SyntheticNote from '@/components/SyntheticNote.vue'
import DxButton from '@/components/ui/DxButton.vue'
import NoticeBlock from '@/components/ui/NoticeBlock.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import StatusLine from '@/components/ui/StatusLine.vue'
import TextField from '@/components/ui/TextField.vue'
import { dateTime, probability } from '@/lib/format'
import { reviewLabel } from '@/lib/nav'
import { reviewReason } from '@/lib/plate'
import { judgePlate, ltrPlate } from '@/lib/typed'
import { useServiceStore } from '@/stores/service'

const service = useServiceStore()
const EXAMPLE = ltrPlate('24830-ب-1')
const items = ref<ReviewItemOut[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const drafts = reactive<Record<string, string>>({})
const touched = reactive<Record<string, boolean>>({})
const serverErrors = reactive<Record<string, string>>({})
const busy = reactive<Record<string, boolean>>({})
const decided = ref<{ id: string; plate: string | null; action: string }[]>([])
const exporting = ref(false)
const exported = ref<ExportOut | null>(null)
const exportError = ref<string | null>(null)

const title = computed(() =>
  reviewLabel(
    service.review ?? (loading.value ? null : { pending: items.value.length, ready_to_export: 0 }),
  ),
)
const ready = computed(() => service.review?.ready_to_export ?? 0)
const exportLabel = computed(() => {
  if (ready.value === 0) return 'No corrections to export'
  return `Export ${ready.value} ${ready.value === 1 ? 'correction' : 'corrections'}`
})

/** What the typed correction reads as, judged by the plate automaton while it is typed. */
function judgement(item: ReviewItemOut) {
  const draft = drafts[item.id] ?? ''
  if (!draft.trim()) return null
  return judgePlate(draft)
}

function fieldError(item: ReviewItemOut): string | null {
  if (serverErrors[item.id]) return serverErrors[item.id] ?? null
  const judged = judgement(item)
  if (judged && !judged.valid && touched[item.id]) return judged.message
  return null
}

function fieldHint(item: ReviewItemOut): string {
  const judged = judgement(item)
  if (judged?.valid) return judged.message
  return `Type the plate as it reads on the crop, for example ${EXAMPLE}, or confirm the read.`
}

async function load() {
  loading.value = true
  try {
    items.value = await api.reviewQueue(100)
    error.value = null
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
  void service.refreshReview()
}

async function decide(item: ReviewItemOut, confirm: boolean) {
  delete serverErrors[item.id]
  touched[item.id] = true
  const plate = (drafts[item.id] ?? '').trim()
  if (!confirm) {
    const judged = judgePlate(plate)
    if (!judged.valid) {
      serverErrors[item.id] = judged.message
      return
    }
  }
  busy[item.id] = true
  try {
    const out = await api.decide(item.id, confirm ? { confirm: true } : { plate })
    items.value = items.value.filter((i) => i.id !== item.id)
    decided.value.unshift({
      id: item.read_id,
      plate: out.corrected_plate ?? out.plate,
      action: confirm ? 'Confirmed' : 'Corrected',
    })
    void service.refreshReview()
  } catch (cause) {
    serverErrors[item.id] = errorMessage(cause)
  } finally {
    busy[item.id] = false
  }
}

async function exportReviewed() {
  exporting.value = true
  exportError.value = null
  try {
    exported.value = await api.exportReviewed()
    void service.refreshReview()
  } catch (cause) {
    exportError.value = errorMessage(cause)
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>{{ title }}</h1>
      <p>
        Reads whose set is not a single plate, or whose confidence is under the service's threshold,
        wait here. Confirm the read or type the plate as it appears on the crop; reviewed crops
        export as labelled training data in the <code>data/ocr/train</code> layout.
      </p>
    </header>

    <div class="toolbar">
      <DxButton
        variant="primary"
        :icon="Download"
        :disabled="ready === 0 && !exporting"
        :busy="exporting"
        busy-label="Exporting"
        data-testid="export-button"
        @click="exportReviewed"
      >
        {{ exportLabel }}
      </DxButton>
      <p v-if="exported" class="dx-footnote done-line" role="status" data-testid="export-result">
        Exported {{ exported.exported }} crop(s) to <code>{{ exported.path }}</code
        >.
      </p>
      <NoticeBlock
        v-if="exportError"
        tone="error"
        title="The export failed"
        :message="`${exportError} Nothing was marked as exported; try again.`"
      />
    </div>

    <section aria-labelledby="queue-title" class="dx-section">
      <div class="dx-section-head">
        <h2 id="queue-title">Waiting for review</h2>
        <DxButton variant="plain" size="small" @click="load">Check for new reads</DxButton>
      </div>
      <SkeletonBlock v-if="loading" kind="table" :rows="3" label="Loading the queue" />
      <NoticeBlock
        v-else-if="error"
        tone="error"
        title="The queue is unavailable"
        :message="`${error} Reads queued meanwhile are kept and appear when it answers.`"
      />
      <p v-else-if="items.length === 0" class="dx-secondary">
        Reads the service cannot certify wait here for a person. Nothing is waiting now.
      </p>
      <ul v-else class="queue">
        <li
          v-for="item in items"
          :key="item.id"
          class="item"
          data-testid="review-item"
          :data-read-id="item.read_id"
        >
          <div class="crops">
            <img
              v-for="(crop, index) in item.crops"
              :key="crop"
              :src="serviceUrl(crop)"
              :alt="`Crop ${index + 1} of the read`"
            />
            <p v-if="item.crops.length === 0" class="dx-secondary dx-footnote">No crop was kept.</p>
          </div>
          <div class="body">
            <div class="proposed">
              <span class="dx-plate plate">{{ item.plate ?? 'No plate read' }}</span>
              <StatusLine tone="warn" :label="reviewReason(item.reason)" />
            </div>
            <dl class="dx-facts">
              <dt>Confidence</dt>
              <dd>{{ probability(item.confidence, 1) }} calibrated on synthetic plates</dd>
              <dt>Set</dt>
              <dd>
                <template v-if="item.prediction_set === null">not calibrated</template>
                <template v-else-if="item.prediction_set.length === 0">empty</template>
                <span v-else class="chips">
                  <span v-for="plate in item.prediction_set" :key="plate" class="chip dx-plate">{{
                    plate
                  }}</span>
                </span>
              </dd>
              <dt>Queued</dt>
              <dd>
                {{ dateTime(item.created_at) }} ·
                <RouterLink :to="`/reads/${item.read_id}`">the read</RouterLink>
              </dd>
            </dl>
            <form class="decide" novalidate @submit.prevent="decide(item, false)">
              <TextField
                :id="`plate-${item.id}`"
                :model-value="drafts[item.id] ?? ''"
                label="Correct plate"
                plate
                :placeholder="EXAMPLE"
                :hint="fieldHint(item)"
                :error="fieldError(item)"
                data-testid="correction-input"
                @update:model-value="(value: string) => (drafts[item.id] = value)"
                @blur="touched[item.id] = true"
              >
                <template #after>
                  <DxButton
                    type="submit"
                    variant="primary"
                    :busy="busy[item.id]"
                    busy-label="Saving"
                    data-testid="save-correction"
                  >
                    Save correction
                  </DxButton>
                  <DxButton
                    variant="secondary"
                    :disabled="item.plate === null || busy[item.id]"
                    @click="decide(item, true)"
                  >
                    Confirm read
                  </DxButton>
                </template>
              </TextField>
            </form>
          </div>
        </li>
      </ul>
    </section>

    <section v-if="decided.length" class="dx-section" aria-labelledby="done-title">
      <h2 id="done-title">Reviewed in this session</h2>
      <ul class="done" data-testid="decided">
        <li v-for="entry in decided" :key="entry.id">
          {{ entry.action }} as <span class="dx-plate">{{ entry.plate }}</span> ·
          <RouterLink :to="`/reads/${entry.id}`"
            ><code>{{ entry.id.slice(0, 8) }}</code></RouterLink
          >
        </li>
      </ul>
    </section>

    <SyntheticNote
      detail="Confidences and sets come from a recogniser calibrated on synthetic plates."
    />
  </div>
</template>

<style scoped>
.toolbar {
  display: grid;
  justify-items: start;
  gap: var(--dx-space-2);
}

.done-line {
  color: var(--dx-success);
}

.queue {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
  border-top: var(--dx-line) solid var(--dx-border);
}

.item {
  display: grid;
  grid-template-columns: minmax(0, 15rem) minmax(0, 1fr);
  gap: var(--dx-space-5);
  padding: var(--dx-space-5) 0;
  border-bottom: var(--dx-line) solid var(--dx-border);
}

.crops {
  display: grid;
  align-content: start;
  gap: var(--dx-space-2);
}

.crops img {
  display: block;
  width: 100%;
  border-radius: var(--dx-radius-control);
  background: var(--dx-surface-inset);
}

.body {
  display: grid;
  gap: var(--dx-space-3);
  min-width: 0;
}

.proposed {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--dx-space-2) var(--dx-space-4);
}

.plate {
  font-family: var(--dx-font-display);
  font-size: var(--dx-text-title);
  letter-spacing: var(--dx-track-title);
}

.chips {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--dx-space-1);
}

.chip {
  padding: 0 var(--dx-space-2);
  border: var(--dx-line) solid var(--dx-border-strong);
  border-radius: var(--dx-radius-control);
}

.decide {
  max-width: 40rem;
}

.decide :deep(.input) {
  flex: 0 1 12rem;
  font-size: var(--dx-text-headline);
}

.done {
  display: grid;
  gap: var(--dx-space-1);
  margin: 0;
  padding-left: var(--dx-space-4);
}

@media (max-width: 720px) {
  .item {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--dx-space-3);
  }

  .decide :deep(.input) {
    flex-basis: 100%;
  }
}
</style>
