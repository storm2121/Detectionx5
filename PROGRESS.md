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

### M4: read log, review queue, active learning, jobs, observability, Compose — done — 2026-10-18

- Built: `services/api` (FastAPI): `POST /read` (one to ten photos; plate, fields, calibrated
  confidence, conformal set with its level, per-view hypotheses, per-character posteriors,
  model version, review state; `detect=false` reads photos as crops), `GET /reads`,
  `GET /reads/{id}`, `GET /reads/{id}/views/{index}/crop`, `GET /review/queue`,
  `POST /review/{id}` (corrected plate, validated by the grammar, or a confirmation),
  `POST /review/export` (reviewed crops plus `labels.csv` rows in the `data/ocr/train`
  layout), `POST /jobs` (folder or video under `PLATE_JOBS_ROOT`), `POST /jobs/upload`,
  `GET /jobs/{id}`, `GET /jobs/{id}/events` (Server-Sent Events), `GET /models`,
  `GET /health`, `GET /metrics`. SQLAlchemy 2 models with an explicit Alembic migration
  (applied at start-up; SQLite by default, PostgreSQL in Compose); the engine is
  `PlatePipeline` plus the review policy; RQ jobs for folders (one read per photo) and videos
  (sampling, greedy IoU tracking, per-track fusion of the best crops), with progress on the
  job row; an RQ worker entry point (`python -m services.api.worker`, `SimpleWorker` on
  Windows). `plate_reader/telemetry.py` (a span and a histogram per stage, request latency,
  confidence and set-size histograms, read and job counters, review-queue gauge).
  `models/detector.onnx` (`plate export detector`: NMS-free one-to-one head, dynamic shape)
  with `OnnxPlateDetector`, which letterboxes like Ultralytics' predictor; parity test
  against the PyTorch detector. `plate registry promote|list` and `models/registry.json`.
  `Dockerfile.api`, `Dockerfile.worker` (torch-free), `Dockerfile.dashboard` (placeholder),
  `docker-compose.yml` (api, worker, redis, postgres, otel-collector, prometheus, grafana,
  dashboard) with the collector, Prometheus and Grafana provisioning under `docker/` and the
  dashboard in `docs/grafana/dashboard.json`; `tools/demo_read.py`; `just api`, `just worker`,
  `just export`, `just train-crnn`, `just demo` (and `just dashboard`, which says M5).
  README run section with the host-port table; ADR 0005 as built; data guide updated.
- Commands run and results:
  - `uv run pytest tests/test_service.py tests/test_tracking_registry.py`: 20 passed
    (every endpoint with a fake recogniser and detector, SQLite and an in-process RQ queue on
    fakeredis; the review round trip ends with a validated `labels.csv` under a temporary
    `data/ocr/train`; folder, video and uploaded-video jobs; SSE; path traversal, missing
    files and a missing queue; Alembic upgrade and downgrade; the tracker's hypothesis
    property; the registry; ONNX-versus-PyTorch detector parity on `samples/car.jpg`).
  - `docker compose build api worker dashboard` then `docker compose up -d`: all eight
    services started; api, postgres and redis healthy. `curl localhost:8100/health`:
    status ok, database ok, queue ok, detector true. `uv run python tools/demo_read.py` (a
    synthetic street scene through the ONNX detector and the CRNN) and
    `tools/demo_read.py --crop --views 3` both returned the generated plate with a singleton
    conformal set. `/metrics` shows the stage histograms, read counters and the review-queue
    gauge; Prometheus scrapes the API and the collector's span metrics (both targets up);
    Grafana 12 is healthy with the provisioned dashboard; the dashboard placeholder serves on
    5174. A synthetic video uploaded to `POST /jobs/upload` went through Redis to the worker
    and came back as one track with the right plate, with SSE progress events. The stack was
    then stopped (`docker compose down`). The Docker engine crashed once during the first
    build (the machine is shared and memory was short); Docker Desktop was restarted and the
    build and checks then succeeded.
  - `just check`: green, 198 passed, 1 skipped, coverage 93.8% on `plate_reader`.
- Decisions: the detector ONNX export uses `nms=False` (the one-to-one head the PyTorch path
  selects) and dynamic height and width, because padding to a square instead of
  Ultralytics' minimum rectangle changed confidences noticeably; the service fuses with unit
  weights (ADR 0009); empty conformal sets are queued only with `PLATE_REVIEW_EMPTY_SETS`;
  job progress lives on the job row and SSE polls it, which works on SQLite and PostgreSQL
  and survives worker restarts; workers receive the API's settings with each job. ADR 0005.
- Stubbed or skipped, and why: the dashboard service is a static placeholder page (M5).
  Traces reach the collector and become span metrics in Prometheus; there is no trace store
  (Tempo or Jaeger) because the architecture's Compose list has none. The CI workflow does
  not build the images yet (Docker build is listed for CI in ARCHITECTURE §14).
- Open questions for the architect: add a trace store to Compose? Default `PLATE_ALPHA` for
  the service given the empty-set behaviour (ADR 0004)?
- Next: M5 (stop here per AGENT_RULES §5.4).

### Review follow-ups after M4 (architect review of M0 to M4) — done — 2026-10-18

- Built: (1) ADR 0009 marked accepted; a note under M3 in `MILESTONES.md` records that the DoD
  is met in spirit. (2) The service serves conformal sets at alpha 0.05 (`PLATE_ALPHA`), and
  empty sets go to review by default (`PLATE_REVIEW_SKIP_EMPTY_SETS` opts out);
  `docs/methods/fusion.md` explains empty sets in two sentences. (3) `docs/data_card.md`
  (first version) and the model card state the assumption that temporary plates carry one to
  six digits. (4) The model card carries the architect's attribution sentence for the
  detector's training data. (5) Grafana Tempo under the Compose `tracing` profile with a
  provisioned data source; conformal thresholds per number of fused views (K = 1, 3, 5) from
  `plate train calibrate-fused` on a new synthetic multi-view calibration split (seed 1008),
  stored in `models/crnn.json`, with measured fused-set coverage per K in
  `results/calibration_fused.json`, rendered in `docs/methods/fusion.md`. The evaluations were
  re-run with the new thresholds (EasyOCR from the read cache).
- Commands run and results: `plate train calibrate-fused`: exit 0 (fused-set coverage per K
  lands on its level within the interval at both alphas; numbers rendered from results).
  `just check`: green, 200 passed, 1 skipped, coverage 92.4%; after adding a smoke test for
  the fused calibration, `tests/test_training.py`: 6 passed. `docker compose config` with and
  without `--profile tracing`: 8 and 9 services.
- Decisions: the pipeline uses the threshold of the largest calibrated view count not above
  the number of fused views; thresholds are now reported at full precision (they reach about
  1e-16 at five views). The collector's Tempo exporter has retries and queueing disabled so
  the default stack is unaffected.
- Stubbed or skipped: Tempo has not been run yet; it is exercised with the M5 Compose smoke.
- Open questions: none new.
- Next: M5.

### M5: Vue dashboard — done — 2026-10-18

- Built: `apps/dashboard`, the console in Vue 3.5 and TypeScript strict (Vite 6, Pinia, Vue
  Router, PrimeVue 4 with a custom Aura preset on the console's design tokens, D3 7, KaTeX),
  server mode. Pages: Read (drop one to ten photos or try three synthetic photos of one car;
  the detected box drawn on each photo; plate fields; calibrated confidence against the
  review threshold; the conformal set with its empty and several-plate states; one card per
  view with its crop, detector confidence, weight and constrained-beam hypotheses; the fusion
  table; the D3 character heatmap with an accessible table; stored reads at `/reads/<id>`;
  recent reads), Jobs (queue a folder or a video, upload a video, live progress over
  Server-Sent Events, per-photo and per-track results), Review queue (crops, set and reason,
  confirm or correct with the grammar's validation message, export to `data/ocr/train`),
  Evaluation (every recogniser on each committed set with bootstrap intervals, reliability
  diagram, letter confusion matrix, fusion by number of views, paired differences,
  temperature scaling before and after, conformal coverage for one view and per number of
  fused views), Models (active recogniser, detector and service settings, thresholds per
  number of views, the registry, the training curve), Methods (the equations in KaTeX, with
  the measured coverage). Light and dark themes (system preference until the viewer picks),
  phone width, a skip link, and the synthetic label on every page. Vitest unit, component
  and page tests (42), Storybook stories for the parts and charts, Playwright smoke and axe
  checks against Compose (34). Service additions: `GET /jobs`, `GET /results`,
  `GET /results/{name}`; the API image carries `results/*.json` and the registry. The
  dashboard image is a Node build stage and nginx forwarding `/api` to the service.
  `make_scene_views` (several street photos of one car) and end-to-end parity fixtures (one
  three-photo set with the Python pipeline's boxes, per-view reads and fused read), which are
  the console's samples, its e2e input and M6's reference.
- Commands run and results:
  - `pnpm build`: vue-tsc (app, node, tests and stories) and Vite build pass.
  - `pnpm test`: 6 files, 42 passed.
  - `pnpm storybook:build`: built; stories render in light and dark (checked by screenshot).
  - `pnpm lint` (ESLint and Prettier): clean.
  - `docker compose --profile tracing up -d` after `docker compose build api worker
    dashboard`, then `pnpm e2e` (Playwright, Chromium, desktop 1440x900 and phone 390x844):
    34 passed: every page in light and dark loads, shows the synthetic label, does not
    scroll sideways and has no axe WCAG 2.1 A/AA violation; three synthetic photos read
    through nginx, the service and the ONNX models give the Python pipeline's fused plate
    and set, with three boxes, three view cards, the fusion table and one outlined heatmap
    cell per character; a queued read is corrected in the review queue, exported, and then
    shows as reviewed; a refused job shows the service's message; the Evaluation page
    switches sets and recognisers; the Models page shows the served model version.
  - Tempo: a `POST /read` trace found through Grafana's Tempo data source with its
    `read`, `detect`, `recognise`, `fuse` and `store` spans (the `tracing` profile works).
  - `just check` (now including `dashboard-check`): green, pytest 207 passed and 1 skipped, coverage 93.7% on `plate_reader`; `plate docs check` and `plate data validate` clean.
- Decisions: the console reads results through the API so it shows the results of the
  models the service loaded; versions are pinned to the majors the code was verified against
  (ADR 0006 implementation notes); plate text uses `unicode-bidi: isolate-override` because
  plain bidi reorders `24830-ب-1`; the fused conformal threshold is chosen by the number of
  views that proposed a plate rather than the number of photos (a photo whose crop yields no
  grammar-valid string contributes nothing to the fusion; no view of the synthetic
  calibration or test sets abstains, so the committed thresholds and results are unchanged;
  ADR 0004 updated). Found and fixed while testing: a first `just api` on a fresh clone failed
  because SQLite cannot create the database folder (the service now creates it), and
  absolutely positioned screen-reader text inside a scrolling table widened the page.
- Stubbed or skipped, and why: the in-browser mode toggle and its parity indicator are M6.
  The Docker engine stopped answering once more (shared machine); Docker Desktop was
  restarted and the builds and checks then succeeded.
- Open questions for the architect: none.
- Next: M6.

### M6: in-browser inference, parity, sim-to-real page, domain-randomisation sweep — done — 2026-10-19

- Built: `apps/dashboard/src/inference`, the in-browser runtime: ONNX Runtime Web 1.22
  (WebGPU when the browser offers an adapter, single-threaded WebAssembly otherwise) running
  `models/detector.onnx` and `models/crnn.onnx` from the console's own static files, with
  TypeScript ports of every step between a decoded PNG and a read: Ultralytics' letterbox,
  OpenCV's BGR-to-grey conversion and `resize` (INTER_LINEAR with OpenCV's fixed-point
  weights and the rounding of its SIMD vertical pass, INTER_AREA with exact block averages,
  float area weights and the area-flavoured bilinear weights), the detector's padding,
  cropping and de-duplication, the temperature log-softmax, the grammar-constrained prefix
  beam search, the beam posterior and conformal set, the threshold per number of proposing
  views, CPython's `math.fsum`, the Levenshtein alignment and the probabilistic fusion with
  per-character posteriors. The Read page has a Server or In this browser toggle; switching
  runs the parity fixtures on the chosen backend and shows the outcome as the parity
  indicator; a browser read has the service's response shape, so every component draws it,
  and it is marked as not stored. `/parity` reads every fixture in the browser and lists the
  largest differences. The Models page shows the sim-to-real gap (synthetic test set against
  the pseudo-real set per recogniser, with a column for real photos once `eval_data`
  exists) and the augmentation sweep. Python side: `plate export web` writes the automaton
  (`src/inference/grammar.json`, with a drift test) and OpenCV reference cases
  (`tests/fixtures/web/opencv_cases.json`); the parity fixtures record the CRNN's 8-bit
  input of every crop and scene view; `plate sweep` (Optuna TPE, 4.x) scales five groups of
  augmentation bounds per trial, fine-tunes the shipped CRNN briefly on crops generated with
  them, and scores a new pseudo-real tuning split (seed 1009) with paired bootstrap
  intervals; `TrainConfig` takes the augmentation preset, initial weights and whether data
  workers persist.
- Commands run and results:
  - `pnpm test`: 8 files, 105 passed (62 of them in `src/inference`: the 40 OpenCV reference cases,
    including 24 random shapes, byte for byte; the constrained beam of all 16 crop fixtures
    from their logits; the fusion of the scene set; `fsum` against CPython's values).
  - Browser parity in Chromium (WebAssembly backend, `vite preview`): 20 of 20 fixtures
    within tolerance; largest CRNN input difference 0 grey levels, largest logit difference
    3.9e-6, largest probability difference 3.6e-7, largest box difference 4.9e-5 px,
    largest detector score difference 8.6e-7; about 6 s for all fixtures.
  - `pnpm exec playwright test e2e/parity.spec.ts` against `vite preview`: 2 passed (the
    parity page passes every fixture; the in-browser mode reads the three sample photos to
    the Python pipeline's plate and set with no request to `/api/read`).
  - `uv run plate sweep`: 8 trials on `cuda` (about 20 minutes), `results/sweep.json` written and rendered in `docs/model_card.md`. Synthetic: the shipped weights score 0.692 [0.663, 0.719] on the 1000 tuning crops; fine-tuning with the shipped configuration (trial 0) gives 0.664 [0.635, 0.692]; the best trial (geometry x1.94, photometry x1.51, noise x1.48, clutter x0.59) gives 0.726 [0.698, 0.750], a paired difference to trial 0 of 0.062 [0.041, 0.085]; synthetic validation stays at about 0.98 for every trial.
  - `uv run pytest tests/test_web.py tests/test_sweep.py tests/test_docs_render.py`: passed.
  - `docker compose build api worker dashboard`, `docker compose --profile tracing up -d --wait`, then `pnpm e2e` (Playwright, desktop and phone): 38 passed (the 34 smoke, accessibility, read and review tests plus the two parity tests on each viewport).
  - `just check`: green; console lint, build, 105 unit tests and Storybook; pytest 226 passed and 1 skipped, coverage 93.9% on `plate_reader`; `plate docs check` and `plate data validate` clean.
- Decisions: the sweep fine-tunes the shipped CRNN per trial instead of training from
  scratch (a from-scratch CRNN needs several full epochs before its accuracy carries any
  signal, and the first from-scratch attempt scored zero at the sweep's budget); it scores a
  separate pseudo-real tuning split so the evaluation set never steers a choice it later
  measures; the best configuration is recorded, not adopted, because adopting it means a
  full retraining and re-calibration. OpenCV 5's INTER_LINEAR applies its SIMD rounding to
  every pixel of a row (found by the reference cases: the scalar tail rounding of OpenCV 4
  would be one grey level off at some widths), and its BGR-to-grey conversion uses 15-bit
  weights. ONNX Runtime Web's WebAssembly binary is bundled by Vite instead of copied, and
  threads are off because a static page has no cross-origin isolation. The models and
  fixtures are served under `/runtime/`: copied to `/models` and `/parity` they shadowed the
  console's pages of the same names, and nginx answered those addresses with a redirect to
  port 80 (found by the Compose smoke run, eight failures on exactly those two pages; nginx
  no longer tries folders for page addresses). ADR 0006 implementation notes (M6), ADR 0010.
- Stubbed or skipped, and why: WebGPU could not be exercised here (headless Chromium offers
  no adapter); the backend selector and the parity check run on it when a browser does. The
  first sweep run crashed when a data worker imported a module that was being edited; a
  second crashed on Windows persistent data workers between trials (fixed by not keeping
  workers alive in the sweep's trainings); the third completed.
- Open questions for the architect: whether to retrain the CRNN with the sweep's best
  configuration (it changes the shipped model, every calibration and every result).
- Next: M7.

### M7: documentation and demo — done — 2026-10-19

- Built: the README rewritten around what the platform does, why it is built this way, two
  Mermaid diagrams (a read, and the deployed stack), how a read works step by step, the
  rendered results (detector, recognisers on synthetic plates, CRNN training and
  calibration, multi-view fusion, the pseudo-real stand-in), how to run it (ports, the
  console, the service's endpoints, the `plate` commands), inserting real data, what changes
  once real data arrives, honesty and limitations, the original reader, development and
  layout. `docs/CV_NOTES.md`: every CV line with the code, tests and results that back it,
  and a rendered table of the figures, each with its source file; it is now a governed
  document (`plate docs check` covers it). Model card and data card v2 (runtimes, per-view-
  count thresholds, the sweep, every split and its seed). ADR 0010 (the sweep). CHANGELOG
  complete through M7. `just demo` waits for the stack to be healthy and reads three
  synthetic photos of one car; `tools/demo_read.py` waits for health and prints the console's
  address. The two detector stubs are now implemented: `plate eval-detector` validates the
  detector with Ultralytics on any `detector.yaml` in the data layout and writes the metrics
  with the set's provenance and counts (`results/eval_detector_synthetic.json` for a
  synthetic scene set, `results/eval_detector_data.json` for real photos), rendered in the
  README, the model card and the CV notes and shown on the console's Models page, with
  `just eval-detector` to reproduce it; `plate train detector` takes `--device`,
  `--workers` and `--amp/--no-amp` and has run for real on a tiny synthetic scene set.
- Commands run and results:
  - Clean clone: `git clone` of the branch into `.cache/clean-clone` (`data/` holding only
    the placeholder), then `just setup && just demo` there. The stack came up healthy (eight
    containers); `tools/demo_read.py` read three synthetic photos of one car as the true
    plate with a single-plate prediction set, three of three views read, not queued for
    review; the console answered on 5174 (`/`, `/models`, `/api/health` and
    `/runtime/models/registry.json` all 200). The clone's stack was then stopped and the
    clone deleted.
  - `uv run plate synth scenes --n 300 --seed 1005 --val-fraction 0.5 --out synthetic/scenes-eval`
    then `uv run plate eval-detector --data synthetic/scenes-eval/detector.yaml`: on the
    validation half (150 scenes, 135 plates, 15 scenes without a plate), precision 0.729,
    recall 0.948, mAP@50 0.843, mAP@50-95 0.602; one Ultralytics pass, so no interval.
    Synthetic results are not real-world accuracy. `just eval-detector` reproduced the same
    values (twice, GPU chosen by Ultralytics).
  - `uv run plate synth scenes --n 64 --seed 1001 --val-fraction 0.25 --out .cache/detector-smoke`
    then `uv run plate train detector --data .cache/detector-smoke/detector.yaml --epochs 1
    --imgsz 320 --batch 8 --workers 2 --weights models/best.pt --project .cache/detector-run
    --device 0 --no-amp`: one real epoch on 48 training scenes, validated on 16, weights
    written under `.cache/detector-run/train/weights` (not committed: one epoch on 16
    validation scenes says nothing about the detector); nothing was downloaded.
  - `PLATE_TEST_MODELS=1 uv run pytest tests/test_detector_runs.py`: 2 passed (Ultralytics
    validation and one training epoch on tiny synthetic scene sets, on the CPU).
  - `just check`: green; console lint, type-check, build, 105 unit tests (8 files) and
    Storybook; ruff, mypy --strict (85 files) and the repository guards; pytest 232 passed
    and 3 skipped (the real-model API test and the two Ultralytics tests, all opt-in),
    coverage 93.98% on `plate_reader`; `plate docs check` and `plate data validate` clean.
  - `docker compose build api worker dashboard`, `docker compose --profile tracing up -d
    --wait`, then `just dashboard-e2e` (Playwright, desktop and phone): 38 passed, with the
    Models page showing the detector's synthetic-scene metrics; the stack was then stopped.
  - `uv run python tools/repo_guards.py names --all` and `data --all`: clean.
- Decisions: the README keeps the original reader's story as a short section, since the
  shims and the EasyOCR baseline are still part of the platform; the CV notes are governed so
  that a CV figure can only come from a results file. The detector's synthetic evaluation
  uses the validation half of a scene set generated from the test seed and records its
  digest; it is labelled synthetic everywhere, and the README says the detector's only
  independent figures are synthetic. Ultralytics' loader workers load in the
  main process for evaluation by default (`--workers`): on Windows its spawned workers died
  once while the clean clone's Compose stack was running. Text now checks out with LF on every
  platform (`.gitattributes`): with Windows' `core.autocrlf`, pre-commit's stash and restore
  had rewritten 109 tracked files with CRLF, which Prettier's check rejects (the index was
  LF throughout, so no content changed).
- Stubbed or skipped, and why: the detector is not retrained, and the one-epoch run's
  weights are not used: the shipped `models/best.pt` stays, because a detector trained on
  procedural scenes would need real photos to show it is better. WebGPU was not exercised
  (headless Chromium offers no adapter). CI has not run on GitHub, since nothing is pushed.
  The sweep's best configuration is recorded, not adopted. The Docker engine stopped
  answering (HTTP 500) twice during the leg and was restarted each time.
- Open questions for the architect: whether to retrain the CRNN with the sweep's best
  configuration (it changes the shipped model, every calibration and every result); whether
  the detector should be fine-tuned on synthetic scenes before real photos exist (its
  synthetic precision is well below its recall, but only real photos can say whether that
  matters).
- Next: the architect's review; real data when it exists (`docs/insert_your_own_data.md`).

### M8: polish (the sweep's best configuration trained in full; the detector note) — partial (the final demo is blocked on the Docker engine) — 2026-10-19

- Built: `plate train crnn --augment-from results/sweep.json` trains with the best sweep
  trial's multipliers applied to the default augmentation bounds exactly as in the sweep and
  records them (`augment_source` in `train_crnn.json`). `plate compare-crnn`
  (`plate_reader/eval/compare.py`) reads two exported CRNNs through the served decoder, each
  with its own calibrated temperature, on the same crops of the synthetic test split (seed
  1005) and the pseudo-real set (seed 1006), and writes `results/crnn_comparison.json` with
  each model's exact match and the paired bootstrap difference; the rule is part of the file.
  The model card has a new rendered section for the comparison, the CV notes list both paired
  differences, the training block names the augmentation a model was trained with, and the
  sweep's tables call trial 0 the default configuration. ADR 0010 is accepted, with an
  outcome section. The detector's precision gap on synthetic scenes is rendered with its
  result (README and model card) and recorded in the data guide as noted, not acted on; the
  detector is not fine-tuned on synthetic scenes, as the architect decided.
- Commands run and results:
  - `uv run plate train crnn --augment-from results/sweep.json --models-dir .cache/crnn-sweep/models --results-dir .cache/crnn-sweep/results`:
    the shipped recipe from scratch (24 epochs of 20000 crops, curriculum, seed 0) on `cuda`
    in 796.5 s; kept epoch 21 (synthetic validation greedy exact match 0.998); temperature
    0.8008; conformal coverage at the 0.90 and 0.95 levels 0.902 [0.8845, 0.917] and 0.9605
    [0.941, 0.9715] on the synthetic test split; thresholds for 1, 3 and 5 fused views fitted.
    Version `3d1b26202da9`. The process returned exit code 127 after writing every output;
    the outputs are complete and consistent, and other `plate` commands exit 0, so it is
    noted here and was not investigated further.
  - The rule was fixed before the comparison ran, with 2000 crops per set (the size of each
    calibration split), 1000 paired resamples and 95% intervals, and the comparison ran once.
    `uv run plate compare-crnn --old models/crnn.onnx --new .cache/crnn-sweep/models/crnn.onnx --new-summary .cache/crnn-sweep/results/train_crnn.json`
    (85 s): on the synthetic test split the shipped weights score 0.9945 [0.9915, 0.9975] and
    the retrained ones 0.9975 [0.9950, 0.9995], a paired difference of 0.0030 [-0.0005,
    0.0065] (nine crops right only with the retrained weights, three only with the shipped
    ones); on the pseudo-real set 0.6675 against 0.7305, a difference of 0.0630 [0.0465,
    0.0790]. The synthetic interval includes zero, so the shipped weights stay. Synthetic
    results are not real-world accuracy.
  - Therefore nothing that depends on the weights was redone: calibration, thresholds, ONNX
    export, parity fixtures, browser parity, evaluations, the registry and every rendered
    number are unchanged. The retrained weights stay in `.cache/crnn-sweep` on this machine
    and are not committed.
  - `just check`: green; console lint, type-check, build, 105 unit tests (8 files) and
    Storybook; ruff, mypy --strict (87 files) and the repository guards; pytest 236 passed
    and 3 skipped (all opt-in), coverage 93.83% on `plate_reader`; `plate docs check` and
    `plate data validate` clean.
  - Clean clone: `git clone` of the branch at `56ac83a` into `.cache/clean-clone`, then
    `just setup` there: exit 0. `just demo` could not run: from early in this leg the Docker
    engine has answered every request with HTTP 500 (one `docker version` takes about four
    minutes to fail), and Docker Desktop was not restarted, as the architect asked. The clone
    stays set up, so `just demo` can run there as soon as the engine answers. The last demo,
    on a clean clone in M7, passed; since then the stack changed only in the Models page's
    detector card, which the Compose end-to-end run covered (38 passed) before this leg.
- Decisions: the comparison uses the decoder and temperature the service would run, so a
  difference is one a user would see; it is paired over the same crops, and the comparison
  size was not changed after the result was known. The pseudo-real set is reported beside
  the deciding split, not used to decide, as the architect's rule says.
- Stubbed or skipped, and why: no cheap stub remained. WebGPU still needs a browser with an
  adapter, and CI on GitHub still needs a push, which stays disabled. The final clean-clone demo waits on the Docker engine (above);
  it is the one M8 item not done.
- Open questions for the architect: whether the adoption rule should also weigh the
  pseudo-real set. The retrained weights are better there with an interval above zero and
  not worse on the synthetic test split within its interval; under the rule as given they
  were not adopted, and adopting them would need the whole chain of re-calibration,
  re-export, parity, evaluations and re-rendering.
- Next: none; this is the last leg.

### Design and product pass: real photos lead, the harness crops as the service does, the console redesign — done — 2026-10-19

- Built (Part A, product): the Read page reads only the viewer's photos (the synthetic
  sample button, the store's sample loader and the sample copy step are gone; the e2e tests
  still upload the parity fixtures, a development path). `just demo` builds and starts the
  stack and prints where the console is (`tools/wait_ready.py`, which sends nothing);
  `just demo-synthetic` keeps the synthetic crops, the small evaluation and the synthetic
  read for CI and development. ADR 0011. The harness crops labelled photos exactly where the
  service crops them, records repository-relative sources, takes `--note` (a description of
  the set, kept in the results) and writes results with LF. The README's results open with a
  rendered Real photos section (every recogniser with its interval, the honest sentence
  about twelve photos and an easy set, the calibration and sets that do not carry over, the
  sim-to-real gap), and the synthetic figures sit under "Development and synthetic harness",
  still labelled; the status line links to the real section. The model card, the CV notes
  and the data card no longer say that no real set exists. `GET /review/summary` (reads
  waiting, corrections ready to export) for the console's navigation and export button.
- The EasyOCR harness discrepancy (item 3). Cause: `_detector_for_photos` truncated the
  detector's float box to whole pixels before `data_set` padded it, while the service pads
  the float box (`detections_from_boxes`); the harness's crop was one pixel off the
  service's on 11 of the 12 photos. Measured per photo (only right or wrong per field was
  printed, never a plate) with `plate read`'s own path (PyTorch detector, EasyOCR on the CPU,
  every detection read and voted) against the harness adapter: served path exact 1 of 12,
  digits 2 of 12, letter 2 of 11, region 2 of 11; harness as committed (truncated box, GPU)
  exact 0, digits 2, letter 2, region 1, differing only on real_12 (the repository's sample,
  whose region it read as 7); harness with the served crop, on the GPU and on the CPU: exact 1,
  digits 2, letter 2, region 2, identical to the served path on every photo. Neither the
  EasyOCR device (CPU runs EasyOCR's quantised models) nor the CLI's vote across several
  detections in one photo (one photo has two) changed any read here. The ONNX detector's
  padded boxes equal the PyTorch detector's on all twelve photos. The low EasyOCR score is
  the served path's real behaviour on these photos, as the architect's own `plate read`
  runs show (one exact read, the rest with at most some fields right).
- Real-set results before and after the fix (`uv run plate eval --set data -r easyocr
  -r crnn-greedy -r crnn-beam --views 0 --note "small and easy (clean rear shots)"`, 155 s,
  CUDA for EasyOCR): exact match EasyOCR path 0 of 12 then 1 (8%, 0 to 25), CRNN greedy 1
  then 3 (25%, 0 to 50), CRNN constrained beam 3 then 4 (33%, 8 to 58); beam digits 42% then
  50%, letter and region 64% before and after, CER 25% before and after. The CRNN was also
  hurt by the one-pixel shift. The beam's ECE on the real photos is 47% (25 to 68) and its
  conformal sets hold none of the twelve truths: the synthetic calibration does not carry
  over (rendered with the results). Synthetic test set for comparison: the beam 99%.
- Commands run and results: `uv run pytest -q tests/test_eval.py tests/test_eval_photos.py
  tests/test_docs_render.py`: 45 passed (the 15 eval tests, 5 new photo tests, the render
  tests with a new real-photos test); `uv run pytest -q tests/test_service.py`: 15 passed;
  `uv run plate docs render` then `plate docs check`: in sync; ruff and mypy --strict clean.
- Built (Part B, the console on `docs/DESIGN.md`; ADR 0012): `src/styles/tokens.css`, one
  tokens file for light, dark (chosen, or followed from the system before a choice),
  reduced transparency and higher contrast: a nine-step neutral ramp, one blue accent,
  success, warning, danger, five equal-lightness categorical hues validated with the dataviz
  validator, materials, the 4 px space scale in rem, the three radii, hairlines on dense
  screens, motion values. The system type stack with optical sizes, size-specific tracking
  and tabular figures everywhere; Noto Naskh Arabic for plate letters at the Latin
  x-height. PrimeVue and its theme are gone: headless controls (button, icon button with a
  tooltip, segmented control, switch, text field with inline validation, native select,
  disclosure, notice, status line, skeleton, progress bar) styled only with tokens; Lucide
  (`@lucide/vue`, the maintained successor of the deprecated `lucide-vue-next`) is the only
  icon set; Motion's `animate` drives pointer-down press feedback and critically damped
  springs that start from the current value, with a cross-fade under reduced motion. A
  translucent top bar with a scroll-edge fade that names the page, a translucent tab bar at
  phone width, "Review queue (3 waiting)" from `GET /review/summary`. The Read page: photos
  and boxes left, the result right (one column on a phone); the plate large in both
  scripts with the character heatmap on the same columns; the calibrated confidence as a
  one-hue ramp bar; the prediction set as chips; the views and the fusion table in a section
  that opens in place; server or browser as a segmented control with the parity check
  beside it; photos reorder by dragging with Pointer Events and capture (1:1 from the grab
  point, rubber-banded at the tray's edges, released into a spring carrying the pointer's
  velocity; touch picks up after a short press) or with the arrow keys. Review queue:
  crops, proposed read, set, an inline correction judged by the plate automaton as it is
  typed, one export button with the count. Jobs: progress bars that spring to each update,
  with a count and a rate. Evaluation and Models open with the real photos (intervals in
  words, `25% (0 to 50)`; the sim-to-real gap as a table, then two bars per recogniser with
  their intervals, labelled with their set); the synthetic sets follow under "Development and
  synthetic harness". Methods at a 70-character measure. Charts use D3 joins eased on the
  spring curve and move by transform and opacity only. Storybook renders every story in both
  themes side by side (stories for every control, the Read parts, the results views and the
  shell). Playwright writes `docs/images/console-<page>-<theme>-<width>.png` for seven pages,
  two themes and two widths (28 images, `just dashboard-screenshots`). A bundle check runs
  after every build (`scripts/check-bundle.mjs`). `docs/DESIGN_NOTES.md` lists every
  departure from the brief and the audit against its §1 list.
- Commands run and results (Part B): `pnpm test` (Vitest): 10 files, 122 passed. `pnpm lint`:
  clean. `pnpm build`: vue-tsc and Vite pass; the bundle check reports a first load of 93 kB
  of script and 6.7 kB of styles, gzipped, against budgets of 110 and 10 (the console before
  the redesign shipped about 121 and 5, measured from a temporary worktree of HEAD).
  `pnpm storybook:build`: built; three stories checked in a browser render a light and a
  dark frame each. Playwright against the production build (`vite preview` on 5174, the
  service on 8100 with SQLite in a scratch folder and exports redirected there, so nothing
  reached `data/`): `e2e/smoke.spec.ts` and `e2e/parity.spec.ts`, desktop and phone, 41
  passed and 1 skipped (every page in both themes loads, labels its synthetic numbers, does
  not scroll sideways and passes axe WCAG 2.1 A/AA; the three-photo read; the review round
  trip and export; the refused job; the evaluation switch; the models and methods; browser
  parity on every fixture; the in-browser read with no upload; the drag-and-drop reorder
  with 1:1 tracking, the settle and the keyboard move back; a reduced-motion pass with axe;
  the drag test is skipped on the phone project, where a drag starts with a long press).
  `pnpm screenshots`: 28 passed. `just check`: green; ruff, mypy --strict (87 files), the
  repository guards, the console's lint, build with the bundle check, 122 unit tests and
  Storybook; pytest 242 passed and 3 skipped (all opt-in), coverage 93.84% on
  `plate_reader`; `plate docs check` in sync; `plate data validate` clean (it now counts the
  twelve local private photos, with no error).
- Decisions: the harness cuts a detected photo at the service's own crop box (its detector
  returns `detect_image` boxes, already padded) and pads only labelled boxes; results carry
  `set.note` for the words that describe a set, so the honest sentence is rendered, not
  typed. The README's real-photo block uses whole per cent with intervals in words (twelve
  photos carry no decimal); the synthetic tables keep their format. The placeholder test now
  checks what the repository ships (the tracked `data/` files laid out on their own), since a
  working copy may hold the private set (it failed on that set before the change). PrimeVue
  removed rather than re-themed (its CSS transitions, shadows and focus rings leaked; ADR
  0012). Every other design decision that departs from or interprets the brief is in
  `docs/DESIGN_NOTES.md` (among them: the type stack names the Segoe UI Variable optical
  instances because Chromium on Windows resolves neither the family nor its opsz axis; "the
  plate in both scripts" is its Latin digits and Arabic letter, with no invented
  transliteration; a phone tab bar instead of a scrolling link row; no sheets exist, so the
  sheet radius is unused; in-table chart marks animate by CSS transitions on the spring
  curve rather than D3 transitions).
- Stubbed or skipped, and why: Docker answered with HTTP 500 at the start of the leg and
  again at its end, and was not restarted, as instructed, so the Compose smoke run, `just demo` and the
  clean-clone demo were not run; the same Playwright suite ran against the production build
  and a local service instead (no Redis, so jobs were refused before queueing and no job
  ran end to end; the refused-job test covers the page). WebGPU still needs a browser with
  an adapter. The categorical chart hues are defined and validated but no chart uses them
  yet. Touch drag was checked by its logic and a long-press design, not on a touch device.
- Open questions for the architect: AGENT_RULES §6 still describes `just demo` with the
  synthetic steps that moved to `just demo-synthetic` (ADR 0011); whether to update it. The
  conformal sets cover none of the twelve real photos and the beam's real ECE is high:
  whether to collect real calibration photos next, before any fine-tuning. `docs/images`
  adds about 9 MB of screenshots to the repository; whether to keep them in git or move them
  to an artefact store.
- Next: the architect's review.
