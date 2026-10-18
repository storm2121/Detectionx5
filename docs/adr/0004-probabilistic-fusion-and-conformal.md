# ADR 0004: probabilistic multi-view fusion and conformal prediction sets

Status: accepted (architect, 2026-10-18); expanded during M0, M2 and M3 by the executing agent.

## Context

The current vote sums heuristic weights over strings and reports the winner's share as a
"confidence" that is not a probability. Users need to know when to trust a read and when
to send it for review.

## Decision

- Per view, the recogniser's grammar-constrained beam gives hypotheses with
  log-probabilities. The reported per-view distribution is the beam renormalised over its
  grammar-valid strings, which is the model's posterior conditioned on the output being a
  plate (the beam approximates the normaliser).
- Fusion (`plate_reader/fusion.py`, equations in `docs/methods/fusion.md`): candidates are
  the union of the views' grammar-valid hypotheses; each view's distribution is
  renormalised over the candidate set with a floor for strings it did not propose; the
  fused score is the weighted sum of per-view log-probabilities with weights from detector
  confidence and image quality; the posterior is the softmax of the scores. Per-position
  character posteriors come from Levenshtein alignment of every hypothesis to the winner.
  The legacy vote stays selectable and is reported side by side.
- Calibration by temperature scaling (ADR 0003), fitted on a held-out synthetic split.
- Split conformal prediction: nonconformity is one minus the calibrated probability of
  the true string, computed as the summed probability of the *other* candidates so that
  very confident reads do not collapse to exact ties at zero in floating point; the
  conservative quantile at level 1 - alpha on a calibration split gives the threshold;
  the prediction set is every beam string whose nonconformity is under it. Coverage and
  mean set size are reported at alpha 0.1 and 0.05. The coverage interval is a bootstrap
  over both the calibration and the test split, so it includes the variability of the
  threshold itself.

## As built (M2 and M3)

- `fusion.probabilistic_fusion` implements the product of renormalised per-view posteriors
  with a floor for unproposed candidates and per-view weights as exponents (logarithmic
  opinion pooling); with unit weights and conditionally independent views it is Bayes' rule
  under a uniform prior over the candidates (`docs/methods/fusion.md`). Sums use
  `math.fsum` and ties break on the token string, so permutation invariance holds exactly.
- Weights are exponents on each view's evidence. With one view the argmax is preserved for
  any weight, but the probabilities are tempered unless the weight is one; that is why the
  service fuses with unit weights by default and quality weighting (sharpness and detector
  confidence) is an option the harness measures (`probabilistic_weighted`).
- The fused read can carry a conformal set: the single-view threshold applied to the fused
  posterior. The guarantee is only established for single views; the harness reports the
  empirical coverage of the fused sets on the multi-view synthetic sets.
- Observed on the synthetic splits: the CRNN is right far more often than 1 - alpha, so
  split conformal at alpha 0.1 returns an empty set for roughly the excess fraction of
  images (coverage still lands on its nominal level). An empty set means even the best
  candidate is less conforming than the calibration quantile. The review policy queues sets
  with more than one string (as specified); queueing empty sets is a service setting
  (`PLATE_REVIEW_EMPTY_SETS`), off by default, and a smaller alpha is the better lever for a
  model this accurate. Open question for the architect.
- Defaults follow calibration (ADR 0009): `pipeline.PlatePipeline` (the calibrated CRNN
  path the service builds on) fuses probabilistically by default with the vote selectable;
  the original EasyOCR `read_images` uses `fusion="auto"`, which falls back to the vote
  because EasyOCR's vote shares are not calibrated and the vote measures better for them on
  the multi-view synthetic sets.

## Consequences

The API returns a set and a calibrated probability; the review queue has a principled
trigger (set size above one or probability under a threshold); the method is documented
with equations and property tests (permutation invariance, single-view consistency,
monotonicity in weights).
