# ADR 0010: the augmentation sweep fine-tunes and scores a separate pseudo-real split

Status: accepted (architect, M8, 2026-10-19), with the adoption rule below; proposed by the
executing agent in M6.

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

## Outcome (M8)

The architect asked for the best configuration to be trained in full and kept only if it
is better. `plate train crnn --augment-from results/sweep.json` trained it from scratch with
the shipped recipe and calibrated it the same way; `plate compare-crnn` then read the
synthetic test split and the pseudo-real set with both models through the served decoder,
on the same crops, with a paired bootstrap. The rule was fixed before the comparison ran:
the new weights replace the old ones only if the paired difference in exact match on the
synthetic test split has an interval entirely above zero; the pseudo-real set is reported,
not used to decide. The interval on the synthetic test split included zero, so the shipped
weights stayed and nothing that depends on them changed. The pseudo-real difference is in
`results/crnn_comparison.json` and the model card; whether the rule should weigh it is a
question for the architect, not something the comparison settles.
