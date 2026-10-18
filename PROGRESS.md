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

### M1: synthetic plates and the evaluation harness — done — 2026-10-18

- Built: `plate_reader/synthetic/` (bundled OFL fonts with licences and `FONTS.md`;
  `render.py` draws standard and temporary plates from grammar tokens; `augment.py` holds
  every augmentation with its documented, strength-scaled distribution and a heavier
  pseudo-real preset; `backgrounds.py` procedural bodywork and street scenes;
  `generate.py` per-sample seeding from `(seed, kind, index, view)`; `writer.py` writes
  sets in the `data/` layouts with timestamp-free manifests; `splits.py` fixes distinct
  seeds per split); `plate synth crops|scenes|views|pseudo-real`. `plate_reader/eval/`
  (metrics, paired percentile bootstrap, recogniser protocol with the EasyOCR adapter,
  evaluation sets including the real-data `data` path, multi-view fusion at 1, 3 and 5
  views, Plotly HTML report, content-addressed read cache); the legacy vote moved into
  `fusion.py` as the baseline; `plate eval --set synthetic|pseudo_real|data|views`.
  `results/eval_synthetic.json` (EasyOCR path on 300 synthetic crops, legacy vote on 100
  five-view sets) rendered into the README with the synthetic label. CI job: generator
  determinism (`diff -r` of two runs) and a small synthetic evaluation.
- Commands run and results:
  - `plate synth crops --out A --n 40 --seed 5` twice: `diff -r` identical, same digest;
    the digest was unchanged after later lint-only edits to the generator.
  - `plate synth scenes ...` then `plate data validate --root <scenes>`: 0 errors.
  - `plate eval --set synthetic --n 300 --views 100 --k 5 --resamples 1000`: exit 0, about
    14 minutes with EasyOCR on CUDA; numbers in `results/eval_synthetic.json` and the README.
  - `uv run plate docs check`: in sync. `just check`: green, 140 passed, 1 skipped,
    coverage 96.1% on `plate_reader`.
- Decisions: fonts are Barlow Condensed (digits, `W`) and Noto Kufi / Noto Naskh Arabic at
  sampled weights (letter); crops are composed like detector crops (plate warped onto
  bodywork with padding) and degraded at output resolution; a scene set is a complete
  stand-in for `data/` and keeps its synthetic kind through the `data` path because of its
  manifest; CER is computed on printed characters (separators removed) as a corpus rate;
  letter and region accuracy apply to standard plates only (their n is smaller); ECE uses
  ten equal-width bins on the top-prediction confidence; bootstrap intervals are paired
  across recognisers (one index matrix per population); the legacy vote reproduces
  `pipeline.read_images` exactly (detector confidence 1 for crops). The `.gitignore` rule
  for generated sets is anchored to the root (`/synthetic/`); unanchored, it had hidden the
  generator package from git and ruff until caught before commit.
- Stubbed or skipped, and why: detector mAP through Ultralytics validation on synthetic
  scenes (ARCHITECTURE §9) is not implemented yet; the `data` set path crops labelled boxes
  or runs a supplied detector, but no mAP is computed. The CI workflow has not run on
  GitHub (nothing is pushed). `--set data` has only been exercised on synthetic scene sets.
- Open questions for the architect: the pseudo-real preset's strength is a guess until real
  photos exist; calibrating it against real crops is what M6's sweep is for.
- Next: M2 (CRNN, constrained decoding, calibration, conformal sets, ONNX).
