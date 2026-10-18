# ADR 0002: synthetic first, real data as a placeholder

Status: accepted (architect, 2026-10-18); expanded during M0 and M1 by the executing agent.

## Context

The original training images are not on this machine, the firm's photos are private, and
the public README already states that OCR accuracy is not benchmarked. The platform must
be fully runnable and measurable without any real data, and the eventual real data must
drop into a documented place.

## Decision

- A deterministic synthetic plate generator (`plate_reader/synthetic/`) provides crops,
  scenes, multi-view sets and a pseudo-real set; bundled fonts are SIL OFL 1.1 only and
  their licences ship next to them.
- `data/` holds only `README.md`, `detector.yaml` and the empty layout (`.gitkeep`
  files). `.gitignore` ignores everything else under `data/`; the pre-commit hook and the
  CI test `tests/test_repo_guards.py` fail on any staged image, video, archive or CSV with
  more than 50 rows under `data/`.
- `plate data validate` checks the layout, decodes every image, checks YOLO boxes and
  requires every `plate_text` to be accepted by the grammar with a matching `format`. An
  empty layout is valid.
- Every synthetic metric carries its set kind, n, a bootstrap CI and the model version,
  and every document that shows one carries the sentence "synthetic results are not
  real-world accuracy"; `plate docs check` enforces the sentence and the statement "OCR
  accuracy is not benchmarked on real data" while no real labelled evaluation exists.
- The repository never names the original dataset or its hosting service. The guard in
  `tools/repo_guards.py` stores only SHA-256 digests of the normalised tokens and checks
  every tracked file (pre-commit, CI) and every commit message (commit-msg hook).

## Consequences

Numbers in the README are honest but synthetic until real labels exist; the sim-to-real
gap becomes a visible page rather than a hidden assumption. The earlier commits on `main`
still contain the old credits line; the guard scans the working tree and new commit
messages, not history.
