# ADR 0009: the fusion default follows calibration

Status: accepted by the architect (2026-10-18). Deviates from the letter of MILESTONES M3
("the pipeline uses probabilistic fusion by default") for one code path; the DoD is met in
spirit: probabilistic fusion is the default wherever the views are calibrated, and both
methods stay selectable everywhere.

## Context

Probabilistic fusion (ADR 0004) multiplies per-view posteriors. That is Bayes' rule only
when each view's distribution is a calibrated posterior. The CRNN's constrained beam is
calibrated by temperature scaling; the EasyOCR baseline's per-view "distribution" is its
normalised vote share, which is not (its ECE is reported in `results/eval_synthetic.json`),
and for a segmented read it is a single candidate at share one, which discards the OCR
confidence the legacy vote sums.

Measured on the multi-view synthetic sets (`results/eval_views.json`, rendered in the README
and `docs/methods/fusion.md`): with the CRNN, probabilistic fusion matches the vote's exact
match and has the best-calibrated fused confidence; with EasyOCR, the legacy vote has the
higher exact match at three and five views. Weighting views by image quality, which acts as
an exponent on the evidence, breaks the calibration of a single view (its fused conformal
set loses its coverage).

## Decision

- `plate_reader.pipeline.PlatePipeline` (detect, read every view with a recogniser that
  returns hypotheses, fuse, conformal set) fuses probabilistically by default, with unit
  view weights; `fusion="legacy_vote"` selects the original vote. This is the pipeline the
  service builds on.
- `plate_reader.pipeline.read_images` (the original EasyOCR path behind `cli.py`, `gui.py`,
  `api.py` and `plate read`) defaults to `fusion="auto"`: probabilistic when every view is
  calibrated, otherwise the vote, which for EasyOCR means the vote. `fusion="probabilistic"`
  and `fusion="vote"` force either method.

## Consequences

The platform's calibrated path fuses in probability space by default, as the architecture
intends, and the legacy reader keeps the method that measures better for it. If EasyOCR's
scores are ever calibrated (for example by Platt scaling on real crops), `auto` switches it
to the probabilistic product without a code change.
