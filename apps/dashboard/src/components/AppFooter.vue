<template>
  <footer class="foot">
    <div class="inner">
      <p>
        Every metric, confidence and threshold on these pages was measured or calibrated on
        synthetic data; <strong>synthetic results are not real-world accuracy.</strong>
        Real photos must be calibrated and evaluated on their own before they are trusted.
      </p>
      <p class="dx-muted">DetectionX5 console &middot; AGPL-3.0</p>
    </div>
  </footer>
</template>

<style scoped>
.foot {
  border-top: 1px solid var(--dx-border);
  background: var(--dx-surface);
}

.inner {
  display: grid;
  gap: var(--dx-space-1);
  max-width: var(--dx-content-width);
  margin: 0 auto;
  padding: var(--dx-space-4) var(--dx-gutter) var(--dx-space-5);
  font-size: var(--dx-text-sm);
}
</style>
