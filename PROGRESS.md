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

### M2: CRNN recogniser, constrained decoding, calibration, conformal sets, ONNX — done — 2026-10-18

- Built: `plate_reader/crnn/` (charset derived from the grammar's symbols, the input
  contract in `preprocess.py`, the CRNN in PyTorch, numpy decoders: greedy, CTC prefix beam
  and grammar-constrained prefix beam, an exact CTC forward pass used by the tests,
  temperature scaling fitted on the reported beam posterior, split conformal sets with a
  joint calibration-and-test bootstrap for coverage, an ONNX Runtime wrapper with metadata,
  parity fixtures); `plate_reader/training/` (on-the-fly synthetic stream with a curriculum,
  the training loop with fp16 autocast on CUDA, optional fine-tuning on `data/ocr`, ONNX
  export at opset 17, calibration on three disjoint synthetic splits); `plate train crnn`,
  `plate train calibrate`, `plate train detector` (thin Ultralytics wrapper, not run),
  `plate export onnx`, `plate export fixtures`. Committed `models/crnn.onnx`,
  `models/crnn.json`, `models/crnn.pt` (each under 6 MB), `results/train_crnn.json`,
  `results/calibration_crnn.json`, `results/parity_fixtures.json` with sixteen fixture PNGs
  under `tests/fixtures/parity/`. The harness registers `crnn-greedy`, `crnn-beam` and
  `crnn-beam-unconstrained`; `results/eval_synthetic.json` and `results/eval_pseudo_real.json`
  compare them with the EasyOCR path. Model card v1 (`docs/model_card.md`); README sections
  for the CRNN, its calibration and the pseudo-real set, all rendered.
- Commands run and results:
  - `plate train crnn --epochs 24 --epoch-size 20000 --batch-size 128 --workers 6 --device cuda`:
    CUDA torch on the RTX 3050, about 19 minutes of training plus calibration; exit 0.
    No CPU fallback was needed.
  - Conformal coverage at alpha 0.1 on the synthetic test split, with the joint bootstrap
    interval over the calibration and test splits: the interval contains 0.9 (and the alpha
    0.05 interval contains 0.95); values in `results/calibration_crnn.json` and the README.
  - `uv run pytest tests/test_parity.py`: 3 passed (random-weight export at batch sizes one
    and four, committed ONNX against committed weights, fixtures reproduced).
  - `plate eval --set synthetic --n 300 --views 100 --k 5 -r easyocr -r crnn-greedy
    -r crnn-beam -r crnn-beam-unconstrained` and the same with `--set pseudo_real`: exit 0
    (about 40 minutes, almost all of it the EasyOCR baseline; its reads are now cached).
    On the pseudo-real set the conformal coverage falls far below its level, the expected
    effect of a distribution shift; the tables carry a sentence saying so.
  - `just check`: green, 163 passed, 1 skipped, coverage 93.9% on `plate_reader`.
- Decisions: the TorchScript-based ONNX exporter (`dynamo=False`) because the dynamo
  exporter in torch 2.14 targets opset 18 and above; the temperature is fitted on the beam
  posterior the service reports, by golden-section search, and stays at one on a flat
  objective; nonconformity is computed as the mass of the other candidates so confident
  reads do not tie at zero; the coverage interval resamples calibration and test together.
  `crnn.pt` is committed for the parity test and for fine-tuning. A machine path that leaked
  into `results/train_crnn.json` was replaced by a repository-relative one (and the
  serialiser fixed). See ADR 0003.
- Stubbed or skipped, and why: the detector was not retrained (`plate train detector` is a
  thin Ultralytics wrapper, untested end to end because no real detector data exists); GPU
  training is seeded but not bitwise reproducible (cuDNN LSTM), so the model version is the
  ONNX hash.
- Open questions for the architect: on the synthetic splits the CRNN is right far more often
  than 1 - alpha, so at alpha 0.1 about one read in ten gets an empty conformal set (coverage
  is still on target). Should the service use a smaller alpha, and should empty sets go to
  review? (M4 makes it a setting, off by default, as ARCHITECTURE §11 specifies "more than
  one string".)
- Next: M3.

### M3: multi-view probabilistic fusion — done (one deviation, ADR 0009) — 2026-10-18

- Built: `plate_reader/fusion.py`: `probabilistic_fusion` (union of grammar-valid candidates,
  per-view renormalisation with a floor, weighted log-probability sum, softmax posterior),
  per-position character posteriors from Levenshtein alignment to the winner, optional
  quality weights, fused conformal sets (the single-view threshold on the fused posterior),
  and the legacy vote behind the same interface. `plate_reader.pipeline.PlatePipeline`
  (detect, one view per photo, fuse, conformal set; probabilistic by default, the vote
  selectable; optional tracing hook). `read_images`, `plate read` and `cli.py` take
  `--fusion auto|probabilistic|vote`. The harness fuses the first 1, 3 and 5 views with three
  methods and reports exact match, ECE and fused-set coverage with intervals over sets.
  `docs/methods/fusion.md` (equations, the Bayes argument, the properties);
  `results/eval_views.json` (200 synthetic five-view sets); README, model card and methods
  page render the comparison.
- Commands run and results:
  - `uv run pytest tests/test_fusion.py tests/test_platform_pipeline.py`: all passed
    (hypothesis: exact permutation invariance, single-view consistency, monotonicity in
    weights, posteriors are distributions over valid plates, abstaining views change
    nothing; fixed examples include one where the vote and the product disagree).
  - `plate eval --set synthetic ...` (EasyOCR from the read cache) and
    `plate eval --set views --views 200 --k 5 -r easyocr -r crnn-greedy -r crnn-beam`: exit 0.
  - `just check`: green, 178 passed, 1 skipped, coverage 94.1% on `plate_reader`.
- Decisions: ADR 0009. The measurements showed that the product of per-view posteriors is
  right for calibrated views (CRNN: equal accuracy, best-calibrated fused confidence, fused
  sets keep their level at one view) and wrong for EasyOCR's uncalibrated vote shares, where
  the original vote is more accurate at three and five views. So `PlatePipeline`, which the
  service builds on, fuses probabilistically by default, while `read_images` (the EasyOCR
  path) defaults to `auto`, which falls back to the vote for uncalibrated views. Quality
  weights act as exponents and break single-view calibration (the fused set's coverage at
  one view collapses), so unit weights are the default everywhere. ADR 0004 updated.
- Stubbed or skipped, and why: nothing stubbed. Process note: scratch copies of this
  milestone's files were deleted from the scratchpad, which another process shares, while
  M2 and M3 were being separated; the files were recreated from the edits recorded in the
  session and every test above ran on the recreated code. Scratch work now lives in a
  uniquely named directory.
- Open questions for the architect: (1) ADR 0009 deviates from the letter of the M3 DoD for
  the EasyOCR path; confirm or overrule. (2) Should fused prediction sets get their own
  conformal threshold per number of views once real multi-photo sets exist?
- Next: M4.
