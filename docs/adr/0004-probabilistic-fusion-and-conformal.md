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

## Consequences

The API returns a set and a calibrated probability; the review queue has a principled
trigger (set size above one or probability under a threshold); the method is documented
with equations and property tests (permutation invariance, single-view consistency,
monotonicity in weights).
