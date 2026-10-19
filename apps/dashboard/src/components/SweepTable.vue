<script setup lang="ts">
import { computed } from 'vue'

import type { Estimate } from '@/api/results'
import { fixed, percent } from '@/lib/format'

export interface SweepTrial {
  number: number
  multipliers: Record<string, number>
  pseudo_real_exact_greedy: number
  pseudo_real_ci?: [number, number]
  difference_vs_trial_0?: Estimate | null
  synthetic_val_exact_greedy: number
  seconds: number
}

export interface SweepResult {
  label: string
  objective: string
  budget: {
    trials: number
    epochs: number
    epoch_size: number
    tune_size: number
    device: string
  }
  groups: Record<string, string[]>
  init_weights?: string | null
  shipped_before_fine_tuning?: Estimate | null
  baseline: SweepTrial
  best: SweepTrial
  trials: SweepTrial[]
  adopted: boolean
  note: string
}

const props = defineProps<{ sweep: SweepResult }>()

const groups = computed(() => Object.keys(props.sweep.groups))
const ranked = computed(() =>
  [...props.sweep.trials].sort(
    (a, b) => b.pseudo_real_exact_greedy - a.pseudo_real_exact_greedy || a.number - b.number,
  ),
)

function points(value: number): string {
  const p = value * 100
  return `${p > 0 ? '+' : ''}${p.toFixed(1)}`
}

function difference(trial: SweepTrial): string {
  const d = trial.difference_vs_trial_0
  if (!d || trial.number === props.sweep.baseline.number) return '–'
  return `${points(d.value)} (${points(d.ci_low)} to ${points(d.ci_high)})`
}
</script>

<template>
  <div class="sweep" data-testid="sweep-table">
    <p class="dx-small dx-muted">
      {{ sweep.trials.length }} short
      {{ sweep.init_weights ? 'fine-tunings of the shipped CRNN' : 'trainings' }}
      ({{ sweep.budget.epochs }} epochs of {{ sweep.budget.epoch_size }} synthetic crops each),
      scored by exact match on {{ sweep.budget.tune_size }} pseudo-real tuning crops with 95%
      bootstrap intervals. Multipliers scale groups of the generator's degradation bounds; trial
      {{ sweep.baseline.number }} uses the shipped configuration, and differences are paired against
      it.
      <template v-if="sweep.shipped_before_fine_tuning">
        The shipped weights score {{ percent(sweep.shipped_before_fine_tuning.value, 1) }} before
        any fine-tuning.
      </template>
      {{
        sweep.adopted
          ? 'The best configuration is in use.'
          : 'The shipped model still uses the default configuration.'
      }}
    </p>
    <div class="dx-scroll-x" role="region" aria-label="Augmentation sweep" tabindex="0">
      <table class="dx-table">
        <thead>
          <tr>
            <th scope="col">Trial</th>
            <th v-for="group in groups" :key="group" scope="col" class="dx-right">{{ group }}</th>
            <th scope="col" class="dx-right">Pseudo-real</th>
            <th scope="col" class="dx-right">Versus trial {{ sweep.baseline.number }} (points)</th>
            <th scope="col" class="dx-right">Synthetic val</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="trial in ranked"
            :key="trial.number"
            :class="{ best: trial.number === sweep.best.number }"
          >
            <th scope="row">
              {{ trial.number }}
              <span v-if="trial.number === sweep.best.number" class="tag">best</span>
              <span v-else-if="trial.number === sweep.baseline.number" class="tag muted">
                shipped
              </span>
            </th>
            <td v-for="group in groups" :key="group" class="dx-right dx-num">
              {{ fixed(trial.multipliers[group], 2) }}
            </td>
            <td class="dx-right dx-num">
              <strong>{{ percent(trial.pseudo_real_exact_greedy, 1) }}</strong>
              <span v-if="trial.pseudo_real_ci" class="dx-muted dx-ci">
                {{ (trial.pseudo_real_ci[0] * 100).toFixed(1) }}–{{
                  percent(trial.pseudo_real_ci[1], 1)
                }}
              </span>
            </td>
            <td class="dx-right dx-num">{{ difference(trial) }}</td>
            <td class="dx-right dx-num">{{ percent(trial.synthetic_val_exact_greedy, 1) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.sweep {
  display: grid;
  gap: var(--dx-space-3);
}

tr.best th,
tr.best td {
  background: var(--dx-accent-soft);
}

.tag {
  margin-left: 6px;
  font-size: var(--dx-text-xs);
  font-weight: 600;
  color: var(--dx-accent-strong);
}

.tag.muted {
  color: var(--dx-text-muted);
}
</style>
