# ADR 0004: probabilistic multi-view fusion and conformal prediction sets

Status: accepted (architect, 2026-10-18). Expand during M2 and M3.

## Context

The current vote sums heuristic weights over strings and reports the winner's share as a
"confidence" that is not a probability. Users need to know when to trust a read and when to send it
for review.

## Decision

Fuse per-view beam hypotheses in log-probability space over grammar-valid candidates with
per-view weights; derive per-position character posteriors by alignment; calibrate with temperature
scaling; return conformal prediction sets at a stated level. The legacy vote stays selectable as a
baseline and is reported side by side.

## Consequences

The API returns a set and a calibrated probability; the review queue has a principled trigger (set
size or probability); the method is documented with equations and property tests.
