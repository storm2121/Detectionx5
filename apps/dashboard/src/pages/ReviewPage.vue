<script setup lang="ts">
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api, errorMessage, serviceUrl } from '@/api/client'
import type { ExportOut, ReviewItemOut } from '@/api/types'
import ErrorNote from '@/components/ErrorNote.vue'
import LoadingState from '@/components/LoadingState.vue'
import StatusPill from '@/components/StatusPill.vue'
import SyntheticNote from '@/components/SyntheticNote.vue'
import { dateTime, probability } from '@/lib/format'
import { reviewReason } from '@/lib/plate'

const items = ref<ReviewItemOut[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const drafts = reactive<Record<string, string>>({})
const itemErrors = reactive<Record<string, string>>({})
const busy = reactive<Record<string, boolean>>({})
const decided = ref<{ id: string; plate: string | null; action: string }[]>([])
const exporting = ref(false)
const exported = ref<ExportOut | null>(null)
const exportError = ref<string | null>(null)

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
}

async function decide(item: ReviewItemOut, confirm: boolean) {
  delete itemErrors[item.id]
  const plate = (drafts[item.id] ?? '').trim()
  if (!confirm && !plate) {
    itemErrors[item.id] = 'Type the plate as it reads on the crop, for example 24830-ب-1.'
    return
  }
  busy[item.id] = true
  try {
    const out = await api.decide(item.id, confirm ? { confirm: true } : { plate })
    items.value = items.value.filter((i) => i.id !== item.id)
    decided.value.unshift({
      id: item.read_id,
      plate: out.corrected_plate ?? out.plate,
      action: confirm ? 'confirmed' : 'corrected',
    })
  } catch (cause) {
    itemErrors[item.id] = errorMessage(cause)
  } finally {
    busy[item.id] = false
  }
}

async function exportReviewed() {
  exporting.value = true
  exportError.value = null
  try {
    exported.value = await api.exportReviewed()
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
      <h1>Review queue</h1>
      <p class="dx-lead">
        Reads whose conformal set is not a single plate, or whose confidence is under the service's
        threshold, wait here. Confirm the read or type the plate as it appears on the crop; reviewed
        crops export as labelled training data in the <code>data/ocr/train</code> layout.
      </p>
    </header>

    <SyntheticNote
      detail="Confidences and sets come from a recogniser calibrated on synthetic plates."
    />

    <section class="dx-card toolbar" aria-labelledby="export-title">
      <div>
        <h2 id="export-title">Export reviewed crops</h2>
        <p class="dx-small dx-muted">
          Writes every reviewed read that was not exported yet, with its labels CSV.
        </p>
      </div>
      <Button
        label="Export reviewed"
        severity="secondary"
        :loading="exporting"
        data-testid="export-button"
        @click="exportReviewed"
      />
      <p v-if="exported" class="dx-small export-result" role="status" data-testid="export-result">
        Exported {{ exported.exported }} crop(s) to <code>{{ exported.path }}</code
        >.
      </p>
      <ErrorNote v-if="exportError" :message="exportError" title="The export failed" />
    </section>

    <section aria-labelledby="queue-title" class="dx-stack">
      <div class="dx-row queue-head">
        <h2 id="queue-title">Waiting for review</h2>
        <span class="dx-small dx-muted dx-num">{{ items.length }} item(s)</span>
        <Button label="Refresh" size="small" severity="secondary" text @click="load" />
      </div>
      <LoadingState v-if="loading" label="Loading the queue" />
      <ErrorNote v-else-if="error" :message="error" title="The queue is unavailable" />
      <p v-else-if="items.length === 0" class="dx-card dx-muted">Nothing to review.</p>
      <ul v-else class="queue">
        <li
          v-for="item in items"
          :key="item.id"
          class="dx-card item"
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
            <p v-if="item.crops.length === 0" class="dx-muted dx-small">No crop was kept.</p>
          </div>
          <div class="body">
            <div class="dx-row">
              <span class="dx-plate-text plate">{{ item.plate ?? 'no plate read' }}</span>
              <StatusPill tone="warn" :label="reviewReason(item.reason)" />
            </div>
            <dl class="dx-dl">
              <dt>Confidence</dt>
              <dd class="dx-num">{{ probability(item.confidence, 1) }}</dd>
              <dt>Conformal set</dt>
              <dd>
                <template v-if="item.prediction_set === null">not calibrated</template>
                <template v-else-if="item.prediction_set.length === 0">empty</template>
                <span v-else class="dx-plate-text">{{ item.prediction_set.join(' · ') }}</span>
              </dd>
              <dt>Queued</dt>
              <dd>{{ dateTime(item.created_at) }}</dd>
              <dt>Read</dt>
              <dd>
                <RouterLink :to="`/reads/${item.read_id}`"
                  ><code>{{ item.read_id.slice(0, 8) }}</code></RouterLink
                >
              </dd>
            </dl>
            <form class="decide" novalidate @submit.prevent="decide(item, false)">
              <label :for="`plate-${item.id}`">Correct plate</label>
              <div class="dx-row">
                <InputText
                  :id="`plate-${item.id}`"
                  v-model="drafts[item.id]"
                  class="plate-input"
                  dir="ltr"
                  placeholder="24830-ب-1"
                  autocomplete="off"
                  :invalid="Boolean(itemErrors[item.id])"
                  data-testid="correction-input"
                />
                <Button
                  type="submit"
                  label="Save correction"
                  :loading="busy[item.id]"
                  data-testid="save-correction"
                />
                <Button
                  type="button"
                  label="Confirm read"
                  severity="secondary"
                  outlined
                  :disabled="item.plate === null || busy[item.id]"
                  @click="decide(item, true)"
                />
              </div>
              <p v-if="itemErrors[item.id]" class="dx-small field-error" role="alert">
                {{ itemErrors[item.id] }}
              </p>
            </form>
          </div>
        </li>
      </ul>
    </section>

    <section v-if="decided.length" class="dx-card" aria-labelledby="done-title">
      <h2 id="done-title" class="done-title">Reviewed in this session</h2>
      <ul class="done" data-testid="decided">
        <li v-for="entry in decided" :key="entry.id">
          <RouterLink :to="`/reads/${entry.id}`"
            ><code>{{ entry.id.slice(0, 8) }}</code></RouterLink
          >
          {{ entry.action }} as <span class="dx-plate-text">{{ entry.plate }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.toolbar {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: var(--dx-space-3);
}

.toolbar > :nth-child(n + 3) {
  grid-column: 1 / -1;
}

.export-result {
  color: var(--dx-ok);
}

.queue-head h2 {
  margin-right: var(--dx-space-2);
}

.queue {
  display: grid;
  gap: var(--dx-space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.item {
  display: grid;
  grid-template-columns: minmax(0, 260px) minmax(0, 1fr);
  gap: var(--dx-space-4);
}

.crops {
  display: grid;
  gap: var(--dx-space-2);
  align-content: start;
}

.crops img {
  display: block;
  width: 100%;
  border-radius: var(--dx-radius-s);
  border: 1px solid var(--dx-border);
  background: var(--dx-surface-sunken);
}

.body {
  display: grid;
  gap: var(--dx-space-3);
  min-width: 0;
}

.plate {
  font-size: var(--dx-text-xl);
}

.decide {
  display: grid;
  gap: var(--dx-space-1);
}

.decide label {
  font-weight: 600;
  font-size: var(--dx-text-sm);
}

.plate-input,
.plate-input::placeholder {
  font-family: var(--dx-font-plate);
  font-size: var(--dx-text-lg);
  direction: ltr;
  unicode-bidi: isolate-override;
}

.plate-input {
  width: 12rem;
  max-width: 100%;
}

.field-error {
  color: var(--dx-bad);
}

.done-title {
  margin-bottom: var(--dx-space-2);
}

.done {
  margin: 0;
  padding-left: var(--dx-space-4);
  display: grid;
  gap: var(--dx-space-1);
}

@media (max-width: 640px) {
  .item,
  .toolbar {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
