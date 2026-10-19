# ADR 0010: the augmentation sweep fine-tunes and scores a separate pseudo-real split

Status: proposed by the executing agent (M6, 2026-10-19); the choice of whether to adopt the
best configuration is the architect's.

## Context

MILESTONES M6 asks for `plate sweep`: an Optuna search over augmentation strengths against
the pseudo-real set, with reduced short trainings. Two facts shape it. A CRNN trained from
scratch reads almost nothing for its first epochs of synthetic crops, so a from-scratch
trial short enough for a sweep scores zero whatever its augmentation, and the first attempt
did exactly that. And the pseudo-real evaluation set is what the README reports; a search
that maximised it would report a number it had been tuned on.

## Decision

- A trial scales five groups of `AugmentConfig` bounds (geometry, photometry, blur, noise and
  compression, clutter) by one multiplier each, between one half and two, on a log scale;
  probabilities stay in `[0, 1]`, JPEG quality scales its distance from 100, and a group that
  is off in the default preset (glare) can be switched on.
- Each trial fine-tunes the shipped CRNN (`models/crnn.pt`) on crops generated with its
  configuration at full strength, for a short budget, and is scored by greedy exact match
  on a pseudo-real tuning split with its own seed (`pseudo_real_tune`), never the
  pseudo-real evaluation set. `--scratch` trains from scratch instead.
- The first trial is the shipped configuration; the shipped weights without fine-tuning are
  scored too. Every trial's score has a percentile-bootstrap interval, and its difference to
  the first trial is a paired bootstrap over the same crops, so a ranking within the noise
  is visible as such.
- `results/sweep.json` records every trial and the best configuration with `adopted: false`;
  the model card renders it. Adopting the best configuration means a full training, a new
  calibration, new conformal thresholds and new results, so it is a separate decision.

## Consequences

The sweep is cheap enough to run on one GPU in about half an hour and answers a narrower
question than a from-scratch search: which degradations help the shipped model transfer
further. Once real photos exist, the objective should move to their validation split.
