# ADR 0011: real photos lead the user flow; synthetic data is a development tool

Status: accepted (architect's task brief, 2026-10-19). Deviates from ARCHITECTURE §14,
which describes `just demo` as "synthetic data, eval, compose up", and from the M5 Read page,
which offered three synthetic photos to try.

## Context

A private labelled set of real photos now exists under `data/eval` (gitignored, never
committed), and `plate eval --set data` writes its metrics to `results/eval_data.json`.
Until now everything a visitor met first was synthetic: the Read page's "try three synthetic
photos" button, `just demo` generating crops and evaluating them, and a README whose results
opened with synthetic tables. Synthetic plates remain the right tool for tests, CI, training
and parity, but they are not what the product does for a user, and putting them first
invites reading synthetic scores as accuracy.

## Decision

- The Read page reads the user's photos only. No sample photos ship in the console's public
  folder; the end-to-end tests upload the committed parity fixtures directly, which is a
  development path no user sees.
- `just demo` builds and starts the stack, waits for the service to answer, and prints where
  the console is. `just demo-synthetic` keeps the old recipe (synthetic crops, a small
  synthetic evaluation, the stack, one synthetic read of three photos) for CI and
  development.
- Real-photo results lead: the README's results open with a "Real photos" section, and the
  console's Evaluation and Models pages show the real set first, all rendered from
  `results/eval_data.json` (the README through `plate docs render`, the console through
  `GET /results/eval_data`). Synthetic and pseudo-real results move to a "Development and
  synthetic harness" section below, still carrying "synthetic results are not real-world
  accuracy".
- The harness writes repository-relative paths in its results (`set.source`), so a results
  file never records a machine's folder layout.
- The synthetic generator, the pseudo-real preset and the harness stay as they are: they
  train and calibrate the CRNN, drive the tests and the parity fixtures, and measure the
  sim-to-real gap against the real set.

## Consequences

The first number a visitor reads is a real one, with its interval and n; the synthetic
numbers stay available and labelled for the people who develop the models. The real set is
small, so every real figure carries a wide interval, and the docs say so next to it.
AGENT_RULES §6 still describes the definition of done of the rebuild with the old `just
demo`; that description now applies to `just demo-synthetic`.
