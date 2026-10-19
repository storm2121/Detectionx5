<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { CalibrationResult, FusedCalibrationResult } from '@/api/results'
import CoverageTable from '@/components/CoverageTable.vue'
import MathBlock from '@/components/MathBlock.vue'
import SyntheticNote from '@/components/SyntheticNote.vue'
import { fusedRows, singleViewRows } from '@/lib/coverage'
import { useResultsStore } from '@/stores/results'

const results = useResultsStore()
const calibration = ref<CalibrationResult | null>(null)
const fused = ref<FusedCalibrationResult | null>(null)
const singleRows = computed(() => (calibration.value ? singleViewRows(calibration.value) : []))
const multiRows = computed(() => (fused.value ? fusedRows(fused.value) : []))

const EQ = {
  ctc: String.raw`p_T(s \mid x) = \sum_{\pi \in \mathcal{B}^{-1}(s)} \prod_{t} \operatorname{softmax}\!\Big(\frac{z_t(x)}{T}\Big)_{\pi_t}, \qquad s \in L`,
  beam: String.raw`q_T(s \mid x) = \frac{p_T(s \mid x)}{\sum_{s' \in B_T(x)} p_T(s' \mid x)}`,
  temperature: String.raw`\hat T = \arg\min_{T} \; -\sum_{i=1}^{n} \log q_T(s_i \mid x_i)`,
  floor: String.raw`\tilde p_v(s) = \frac{\max\big(p_v(s), \varepsilon\big)}{\sum_{s' \in C} \max\big(p_v(s'), \varepsilon\big)}`,
  fusion: String.raw`S(s) = \sum_{v} w_v \log \tilde p_v(s), \qquad \pi(s) = \frac{\exp S(s)}{\sum_{s' \in C} \exp S(s')}, \qquad \hat s = \arg\max_{s \in C} \pi(s)`,
  bayes: String.raw`p(s \mid x_1, \dots, x_N) \propto p(s)^{1-N} \prod_{v} p(s \mid x_v)`,
  position: String.raw`P_i(a) = \frac{\sum_{v} \sum_{s \in C} w_v \, \tilde p_v(s) \, [A(\hat s, s)_i = a]}{\sum_{v} \sum_{s \in C} w_v \, \tilde p_v(s) \, [A(\hat s, s)_i \neq \text{none}]}`,
  score: String.raw`r(x, s) = \sum_{s' \neq s} q(s' \mid x) = 1 - q(s \mid x)`,
  quantile: String.raw`\hat q = r_{(k)}, \qquad k = \big\lceil (n + 1)(1 - \alpha) \big\rceil`,
  set: String.raw`\mathcal{C}(x) = \{\, s \in B(x) : r(x, s) \le \hat q \,\}, \qquad \Pr\big(s^\star \in \mathcal{C}(x)\big) \ge 1 - \alpha`,
  ece: String.raw`\mathrm{ECE} = \sum_{b=1}^{10} \frac{n_b}{n} \, \big| \operatorname{acc}(b) - \operatorname{conf}(b) \big|`,
}

const resamples = computed(() => calibration.value?.bootstrap.resamples ?? null)
const bootstrapTex = computed(
  () =>
    String.raw`\big[\hat\theta^{*}_{(0.025)}, \; \hat\theta^{*}_{(0.975)}\big], \qquad \hat\theta^{*}_{b} = \theta\big(\text{resample}_b\big), \; b = 1, \dots, B` +
    (resamples.value ? String.raw`, \quad B = ${resamples.value}` : ''),
)

onMounted(async () => {
  calibration.value = await results.load<CalibrationResult>('calibration_crnn')
  fused.value = await results.load<FusedCalibrationResult>('calibration_fused')
})
</script>

<template>
  <div class="dx-page methods">
    <header class="dx-page-head">
      <h1>Methods</h1>
      <p>
        The mathematics behind every number on the other pages. The same equations, with their
        tests, are in <code>docs/methods/fusion.md</code> and the model card.
      </p>
    </header>

    <SyntheticNote
      detail="The thresholds and coverages quoted here were fitted and measured on synthetic data; real photos must refit them."
    />

    <section class="prose" aria-labelledby="m-read">
      <h2 id="m-read">1. Reading one view</h2>
      <p>
        The CRNN emits one vector of logits <MathBlock :display="false" tex="z_t(x)" /> per frame
        over the blank and the plate symbols. A string's probability sums every CTC alignment
        <MathBlock :display="false" tex="\pi" /> that collapses to it, and the beam search only
        extends prefixes the plate automaton accepts, so every hypothesis is in the plate language
        <MathBlock :display="false" tex="L" />:
      </p>
      <MathBlock :tex="EQ.ctc" />
      <p>
        The reported distribution is the beam renormalised over its grammar-valid strings, the
        model's posterior conditioned on the output being a plate:
      </p>
      <MathBlock :tex="EQ.beam" />
    </section>

    <section class="prose" aria-labelledby="m-temp">
      <h2 id="m-temp">2. Temperature scaling</h2>
      <p>
        One temperature is fitted on a held-out synthetic calibration split by golden-section search
        on <MathBlock :display="false" tex="\log T" />, minimising the negative log-likelihood of
        the true plate under exactly the function reported at inference:
      </p>
      <MathBlock :tex="EQ.temperature" />
      <p>Calibration is checked with the expected calibration error over ten equal-width bins:</p>
      <MathBlock :tex="EQ.ece" />
    </section>

    <section class="prose" aria-labelledby="m-fusion">
      <h2 id="m-fusion">3. Fusing several photos</h2>
      <p>
        Candidates <MathBlock :display="false" tex="C" /> are the strings any view proposed. Each
        view's distribution is renormalised over them with a floor
        <MathBlock :display="false" tex="\varepsilon" />, so one view cannot veto a candidate:
      </p>
      <MathBlock :tex="EQ.floor" />
      <MathBlock :tex="EQ.fusion" />
      <p>
        If the views are conditionally independent given the plate, Bayes' rule gives the product
        below; under a uniform prior over the candidates the prior factor is constant, so with unit
        weights the fused posterior is the normalised product of the per-view posteriors
        (logarithmic opinion pooling).
      </p>
      <MathBlock :tex="EQ.bayes" />
      <p>
        The character heatmap aligns every candidate to the winner (minimum-cost Levenshtein
        alignment) and accumulates the weighted mass each symbol receives at each position:
      </p>
      <MathBlock :tex="EQ.position" />
    </section>

    <section class="prose" aria-labelledby="m-conformal">
      <h2 id="m-conformal">4. Conformal prediction sets</h2>
      <p>
        The nonconformity of a candidate is the probability mass of the other candidates. On a
        calibration split of size <MathBlock :display="false" tex="n" /> the threshold is the
        conservative split-conformal quantile, and the set keeps every beam string under it:
      </p>
      <MathBlock :tex="EQ.score" />
      <MathBlock :tex="EQ.quantile" />
      <MathBlock :tex="EQ.set" />
      <p>
        The guarantee holds under exchangeability between calibration and test reads. A threshold is
        only valid for the kind of read it was calibrated on, so each number of fused views
        <MathBlock :display="false" tex="K" /> has its own threshold
        <MathBlock :display="false" tex="\hat q_K" />. An empty set is a signal, not a bug: no plate
        can be certified at the stated level, so the service sends the read to review by default.
      </p>
      <CoverageTable
        v-if="singleRows.length"
        :rows="singleRows"
        caption="Measured coverage, one view (synthetic conformal and test splits)."
      />
      <CoverageTable
        v-if="multiRows.length"
        :rows="multiRows"
        caption="Measured coverage of fused reads, one threshold per number of views (synthetic multi-view sets)."
      />
    </section>

    <section class="prose" aria-labelledby="m-ci">
      <h2 id="m-ci">5. Uncertainty of the metrics</h2>
      <p>
        Every metric carries a 95% percentile-bootstrap interval over
        <MathBlock :display="false" tex="B" /> resamples of images (or of multi-view sets);
        differences between recognisers resample the same images for both (paired bootstrap), and
        conformal coverage resamples the calibration and the test split jointly.
      </p>
      <MathBlock :tex="bootstrapTex" />
    </section>
  </div>
</template>

<style scoped>
.methods {
  gap: var(--dx-space-7);
}

/* reading text: a 70-character measure and generous leading, equations set flush left */
.prose {
  display: grid;
  gap: var(--dx-space-4);
  max-width: 70ch;
  min-width: 0;
}

.prose p {
  line-height: 1.65;
}

.prose :deep(.math) {
  padding: var(--dx-space-2) 0;
}

/* tables may run wider than the text column; at phone width they scroll in place */
.prose :deep([data-testid='coverage-table']) {
  width: max-content;
  max-width: calc(100vw - 2 * var(--dx-gutter));
}
</style>
