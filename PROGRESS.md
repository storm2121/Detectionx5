# Progress log

Append one entry per milestone (or per blocked item). Record exact commands and pass/fail counts.
Never record the name of the original dataset host.

## Template

### M<n>: <title> — <status: done | partial | blocked> — <date>

- Built:
- Commands run and results:
- Decisions (with ADR ids where relevant):
- Stubbed or skipped, and why:
- Open questions for the architect:
- Next:

## Entries

### Architecture — done — 2026-10-18

- Built: `ARCHITECTURE.md`, `AGENT_RULES.md`, `MILESTONES.md`, ADR stubs 0001–0006, branch `feat/platform-rebuild`.
- Decisions: data stays a placeholder with a validator; grammar automaton as the single source of
  plate formats; CRNN with CTC and constrained beam; probabilistic fusion; conformal sets; Vue 3
  dashboard with in-browser ONNX mode; RQ on Redis; Postgres review queue; OpenTelemetry.
- Next: M0.

### M0: scaffold, guard rails, data placeholder, honest README numbers — done — 2026-10-18

- Built: uv project on Python 3.12 (`pyproject.toml`, `uv.lock`, `.python-version`,
  `requirements.txt` and `requirements-dev.txt` generated from the lock); CUDA 12.6 torch
  on Windows, CPU torch on Linux, headless OpenCV only (ADR 0008). `plate_reader/grammar.py`
  (declarative formats compiled into a 15-state minimal DFA) with `normalize.py` parsing
  through it; every existing module typed for `mypy --strict`; pydantic-settings
  configuration with the same `PLATE_*` names and `config.py` as a shim. The `plate` CLI
  (`read`, `data validate`, `data init`, `docs render`, `docs check`, `version`); `cli.py`
  is a shim over `plate read`. `data/` placeholder (README, `detector.yaml`, empty layout)
  with `plate data validate` and `docs/insert_your_own_data.md`. The render step: README
  detector numbers now come from the epoch-90 row of `docs/training_results.csv` (picked by
  the Ultralytics fitness rule, which selects epoch 90) and the wrong final-epoch table is
  gone. Repository guards (`tools/repo_guards.py`: forbidden dataset-host and dataset-name
  tokens stored only as SHA-256 digests; no real data under `data/`), pre-commit hooks
  (ruff, mypy, both guards, docs check, plus a commit-msg guard), `justfile`,
  `.editorconfig`, CI workflow (lint, guards, type, tests with the 85% gate), CHANGELOG,
  ADRs 0001 to 0006 expanded, ADRs 0007 and 0008 added.
- Commands run and results:
  - `uv run plate --help`: exit 0.
  - `uv run pytest`: 105 passed, 1 skipped (the opt-in real-model API test, as before).
    The original 24 test functions (45 parametrised cases) pass.
  - `uv run mypy plate_reader services`: no issues in 20 source files.
  - `uv run pre-commit run --all-files`: all hooks passed.
  - `uv run plate docs check`: in sync.
  - `git grep -i` for the dataset host name: no match; the guard reports none.
  - `just check`: green; coverage 87.6% on `plate_reader` (gate 85%).
- Decisions: ADR 0001 (automaton; temporary plates accept 1 to 6 digits as the
  architecture says, the old regex took 5 or 6; a whitespace gap inside digits is now
  repaired); ADR 0007 (torch-free serving through ONNX Runtime; torch, Ultralytics and
  EasyOCR in the `ml` dependency group); ADR 0008 (environment). Hand-typed anecdote numbers
  in the README prose (EasyOCR confidences observed on the sample during development) were
  rephrased qualitatively, because they cannot be rendered from results. The CLI is
  assembled from whichever command modules exist so each milestone's commands land with
  their implementation. pytest uses a repo-local `--basetemp=.pytest-tmp` because the
  shared temp root under `%TEMP%` is access-denied on this machine.
- Stubbed or skipped, and why: the real-model API regression test stays opt-in
  (`PLATE_TEST_MODELS=1`), as before. The pre-commit hooks were installed only from the
  guards commit onward, because the hooks validate the staged tree and could not pass until
  the guarded pieces existed; earlier M0 commits were checked by running the relevant tests
  at each commit. CI has not run on GitHub (nothing is pushed); the workflow was exercised
  locally through the same commands.
- Open questions for the architect: confirm the temporary-plate digit range (1 to 6 per
  ARCHITECTURE §5 versus 5 to 6 in the old code) with the firm's experts. The credits line
  for the detector's training data was removed per AGENT_RULES §1.2; if that data's licence
  requires attribution, Mohamed should decide how to satisfy it without naming the source.
  Earlier commits on `main` still contain the old credits line; the guard checks the
  working tree and new commit messages, not history.
- Next: M1 (synthetic plates and the evaluation harness).
