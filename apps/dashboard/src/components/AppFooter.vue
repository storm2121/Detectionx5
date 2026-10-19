<template>
  <footer class="foot">
    <div class="inner">
      <p>
        The recogniser is trained and calibrated on synthetic plates, so its confidence and its sets
        describe synthetic data: synthetic results are not real-world accuracy. Real-photo results
        come from a small labelled set and carry wide intervals.
      </p>
      <p class="dx-tertiary">DetectionX5 · AGPL-3.0</p>
    </div>
  </footer>
</template>

<style scoped>
.foot {
  border-top: var(--dx-line) solid var(--dx-border);
}

.inner {
  display: grid;
  gap: var(--dx-space-1);
  max-width: var(--dx-content-width);
  margin: 0 auto;
  padding: var(--dx-space-5) var(--dx-gutter) var(--dx-space-6);
  color: var(--dx-text-2);
  font-size: var(--dx-text-footnote);
  line-height: 1.45;
}

.inner p:first-child {
  max-width: var(--dx-measure);
}

@media (max-width: 720px) {
  .inner {
    padding-bottom: calc(var(--dx-tab-height) + var(--dx-space-6) + env(safe-area-inset-bottom));
  }
}
</style>
