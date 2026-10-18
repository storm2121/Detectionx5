# DetectionX5 platform: architecture

Status: architecture v1, written 2026-10-18 by the architect session (Fable). The executing agent
builds against this document and `MILESTONES.md`, under `AGENT_RULES.md`. Deviations go through an
ADR in `docs/adr/`.

## 1. What this is

DetectionX5 started as a Moroccan licence-plate reader for a vehicle-expertise firm: a YOLOv10n
detector, separator-bar segmentation, two restricted-alphabet EasyOCR recognisers and a vote across
photos of one car. It becomes a **plate-reading platform that is ready for your data**: a synthetic
plate generator so everything runs with zero real data, an evaluation harness with confidence
intervals, a trained CRNN recogniser with CTC and grammar-constrained decoding, probabilistic fusion
across views, conformal prediction sets with a coverage guarantee, a review queue that closes the
active-learning loop, background jobs for batches and video, observability, a Vue dashboard, and
in-browser inference with parity tests against the Python pipeline.

Real data is a **placeholder until the final step**: a documented folder layout plus a validator.
The repository never names where the original training images came from.

## 2. Principles

1. **Runs with zero real data.** Synthetic plates power tests, CI, the demo and the dashboard.
   Every synthetic metric is labelled as synthetic; the README says it is not real-world accuracy.
2. **No number is typed by hand.** Metrics in docs render from `results/*.json` written by the
   evaluation harness and the training scripts. CI fails on drift.
3. **Probabilities, not strings.** The recogniser outputs per-timestep posteriors; fusion across
   views is done in probability space under the plate grammar; the API returns calibrated confidence
   and a conformal prediction set, never a bare string with a made-up score.
4. **The grammar is a first-class object.** Moroccan formats (standard: digits, one of six Arabic
   letters, region digits; temporary: digits followed by WW) are encoded once as a finite automaton
   used by normalisation, decoding, fusion, the generator and the tests.
5. **Human in the loop by design.** Low-confidence or large-set reads go to a review queue;
   corrections export to the data folder and retrain the recogniser; the registry records every version.
6. **Parity across runtimes.** PyTorch, ONNX Runtime in Python and ONNX Runtime Web in the browser
   must agree on fixtures within tolerance, enforced in CI.
7. **Boring, typed, tested engineering.** Python 3.12 via uv, ruff, mypy, pytest + hypothesis,
   Alembic migrations, conventional commits, ADRs.

## 3. Containers (C4)

```mermaid
flowchart LR
  subgraph Data["data/ (placeholder until the final step)"]
    DET[(detector: YOLO images + labels)]
    OCR[(ocr: crops + labels.csv)]
    EVAL[(eval: photos + labels.csv)]
  end
  SYN[Synthetic plate generator<br/>crops, scenes, multi-view sets]
  CORE[plate_reader core<br/>grammar automaton, detector, segmentation,<br/>EasyOCR baseline, CRNN, fusion, conformal]
  TRAIN[Training: detector (Ultralytics), CRNN (PyTorch)<br/>ONNX export, registry]
  HARN[Evaluation harness<br/>metrics, bootstrap CIs, calibration, HTML report]
  API[FastAPI service<br/>sync reads, jobs, review, registry, metrics]
  WRK[RQ worker on Redis<br/>batch folders, video]
  PG[(PostgreSQL<br/>reads, review queue, exports)]
  OTEL[OpenTelemetry + Prometheus + Grafana]
  UI[Vue 3 + TypeScript dashboard<br/>server mode and in-browser ONNX mode]
  SYN --> HARN
  SYN --> TRAIN
  DET --> TRAIN
  OCR --> TRAIN
  EVAL --> HARN
  TRAIN --> CORE
  CORE --> HARN
  CORE --> API
  API <--> PG
  API <--> WRK
  WRK --> CORE
  API --> OTEL
  API --> UI
  CORE -. ONNX models .-> UI
  PG -. corrections export .-> OCR
```

Compose services: `api`, `worker`, `redis`, `postgres`, `dashboard`, `otel-collector`, `prometheus`, `grafana`.

## 4. Repository layout

```
.
├── ARCHITECTURE.md  AGENT_RULES.md  MILESTONES.md  PROGRESS.md  CHANGELOG.md
├── pyproject.toml  uv.lock  .python-version (3.12)  justfile  .pre-commit-config.yaml
├── plate_reader/                    # core library (existing package, extended)
│   ├── grammar.py                   # the plate automaton: formats, alphabet, validation, enumeration
│   ├── detector.py  segment.py  preprocess.py  normalize.py  ocr.py   # existing, kept and typed
│   ├── crnn/                        # model.py (CNN + BiLSTM + CTC head), charset.py, decode.py (greedy, beam, grammar-constrained beam), calibrate.py (temperature), conformal.py
│   ├── fusion.py                    # multi-view probabilistic fusion + per-position posteriors; legacy vote kept as baseline
│   ├── pipeline.py                  # orchestrates detect -> read (easyocr | crnn) -> fuse -> calibrate -> conformal
│   ├── synthetic/                   # generator: layout, fonts, augmentations, scenes, multi-view sets, labels
│   ├── eval/                        # harness: metrics (exact, per-field, CER, mAP, ECE, coverage), bootstrap, report
│   ├── training/                    # train_detector.py, train_crnn.py, export_onnx.py, registry.py
│   └── telemetry.py                 # OpenTelemetry spans, Prometheus metrics
├── services/api/                    # FastAPI app, SQLAlchemy models, Alembic, RQ jobs, SSE progress
├── apps/dashboard/                  # Vue 3 + TypeScript + Vite + Pinia + PrimeVue + D3 + onnxruntime-web
├── data/                            # PLACEHOLDER: README.md + layout + validator; real files gitignored
│   ├── detector/{images,labels}/{train,val}   data/detector.yaml
│   ├── ocr/{train,val}/labels.csv             # crop_path,plate_text,format
│   └── eval/labels.csv                        # image_path,plate_text,format,x1,y1,x2,y2 (bbox optional)
├── models/                          # best.pt (existing), crnn.onnx, detector.onnx, registry.json
├── results/                         # JSON written by eval/training; docs render from here
├── docs/  adr/  methods/  model_card.md  data_card.md  insert_your_own_data.md  grafana/
├── tests/  (pytest + hypothesis, fixtures are synthetic)
├── .github/workflows/ci.yml  docker-compose.yml  Dockerfile.api  Dockerfile.worker  Dockerfile.dashboard
└── cli.py  gui.py  api.py (thin shims kept for compatibility; logic lives in packages)
```

## 5. The grammar

`plate_reader/grammar.py` defines the Moroccan plate language as an explicit automaton:
standard = `D{1,5} SEP L SEP R{1,2}` with `L ∈ {أ ب د ه و ط}` and `R` the region digits;
temporary = `D{1,6} SEP "WW"`. The module provides `accepts(s)`, `normalize(s)` (reusing
`normalize.py`), `enumerate_completions(prefix)`, a transition function used by the constrained beam
search, and `random_plate(rng, format)` used by the generator. Hypothesis tests assert
`accepts(random_plate())`, idempotent normalisation, and rejection of near-misses (seven letters,
missing separators, letters in digit fields).

## 6. Synthetic plates

`plate_reader/synthetic/`: renders standard and WW plates with bundled OFL fonts (a Latin sans
close to plate lettering and an Arabic font), separator bars, plate frame and bolts; augmentations
with documented distributions: homography (perspective), rotation, scale, motion and Gaussian blur,
noise, JPEG compression, brightness, contrast, shadows, dirt and partial occlusion, colour cast.
Outputs: (a) crops with labels for CRNN training (generated on the fly, deterministic by seed),
(b) small scenes composited on procedural backgrounds with YOLO boxes for detector tests,
(c) multi-view sets: K views of one plate with different augmentations, for fusion evaluation,
(d) a "pseudo-real" set with heavy augmentation that stands in for the sim-to-real gap page until real
data exists, labelled as such everywhere. Hypothesis invariants: every label is grammar-valid,
image sizes within bounds, seeds reproduce byte-identical PNGs.

## 7. Recogniser

- Baseline: the existing segmentation + two EasyOCR recognisers path, kept and evaluated.
- CRNN: a compact CNN (residual blocks, height-collapsing pooling) feeding a two-layer BiLSTM and a
  CTC head over the charset (digits, six Arabic letters, W, separator, blank). Trained in PyTorch on
  synthetic crops with on-the-fly generation and curriculum over augmentation strength; fine-tuned on
  `data/ocr` when present. Mixed precision on GPU, CPU fallback. Export to ONNX (opset 17, dynamic
  batch) with a parity test against PyTorch.
- Decoding: greedy, prefix beam search, and grammar-constrained prefix beam search (the automaton
  prunes transitions). Beam output keeps the top-k strings with log-probabilities.
- Calibration: temperature scaling fitted on a held-out synthetic set (and on real validation when
  present); reliability diagram and ECE in the report.
- Conformal prediction: nonconformity = 1 − calibrated probability of the true string on a
  calibration set; the quantile at level 1 − α gives prediction sets from the beam; coverage and
  average set size reported at α ∈ {0.1, 0.05}.

## 8. Multi-view fusion

Given views v = 1..N (photos and thresholding variants), each with beam hypotheses
H_v = {(s, log p_v(s))}: form the candidate set ∪H_v restricted to grammar-valid strings; score each
candidate by Σ_v w_v · log p̃_v(s) where p̃_v is the per-view distribution renormalised over the
candidate set with a floor ε for unseen strings, and w_v weights by detector confidence and image
quality; choose the argmax; report the posterior over candidates after softmax. Per-position
character posteriors come from aligning every hypothesis to the winner with Levenshtein alignment
and accumulating weighted votes per aligned position, which drives the character heatmap in the UI.
Properties tested with hypothesis: permutation invariance over views, single-view consistency
(fusion of one view returns that view's argmax), monotonicity in weights. The legacy weighted vote
remains as the baseline and the harness reports both on multi-view synthetic sets. Equations live in
`docs/methods/fusion.md`.

## 9. Evaluation harness

`plate_reader/eval/`: inputs are `data/eval/labels.csv` or a synthetic set; metrics: exact match,
per-field accuracy (digits, letter, region), character error rate (Levenshtein), detector mAP@50 and
mAP@50-95 via Ultralytics validation when boxes exist, calibration (ECE, reliability bins), conformal
coverage and set size, latency percentiles; bootstrap CIs by image (1,000 resamples); confusion
matrix for the six letters; comparison tables across recognisers (EasyOCR path, CRNN greedy, CRNN
constrained beam) and across fusion methods (legacy vote, probabilistic). Writes `results/eval_<set>.json`
and an HTML report with Plotly. `plate eval --set synthetic|pseudo_real|data`.

## 10. Training and registry

`plate train detector --data data/detector.yaml` (Ultralytics, config in `training/detector.yaml`,
results and curves to `results/`), `plate train crnn` (synthetic pretrain, optional fine-tune),
`plate export onnx`, `plate registry promote <version>` writing `models/registry.json` (version,
metrics by set, data fingerprint, created_at). The shipped detector is `models/best.pt`; its
validation metrics are read from `docs/training_results.csv` at the epoch that produced it (90) and
rendered into the README; the hand-typed final-epoch table is removed.

## 11. Serving, jobs, review queue, observability

FastAPI (`services/api`): `POST /read` (1–10 photos, synchronous; returns plate, fields, calibrated
confidence, conformal set, per-view hypotheses, per-position posteriors, model version),
`POST /jobs` (folder or video; RQ on Redis; frame sampling and IoU tracking; per-track fusion),
`GET /jobs/{id}` and `GET /jobs/{id}/events` (SSE progress), `GET /reads`, `GET /review/queue`,
`POST /review/{id}` (corrected plate), `POST /review/export` (writes labelled crops to `data/ocr/train`),
`GET /models`, `GET /health`, `GET /metrics`. PostgreSQL via SQLAlchemy 2 + Alembic (SQLite fallback
through `PLATE_DB_URL`). Review policy: enqueue when the conformal set has more than one string or
calibrated confidence is under a threshold. OpenTelemetry spans per stage, Prometheus histograms for
latency and confidence, a Grafana dashboard JSON under `docs/grafana/`.

## 12. Dashboard

`apps/dashboard`: Vue 3, TypeScript strict, Vite, Pinia, Vue Router, PrimeVue components with a
custom theme and design tokens, D3 for calibration curves, confusion matrices and the character
heatmap, KaTeX for equations, onnxruntime-web (WASM, WebGPU when available) for in-browser mode,
pnpm, Vitest, Storybook for Vue, Playwright, axe checks. Pages: Read (drag in several photos; boxes;
fields; per-view hypotheses; fusion table; conformal set; character heatmap; server or in-browser
mode toggle with a parity indicator), Jobs, Review queue, Evaluation (metrics with CIs, calibration,
confusion), Models (registry, sim-to-real gap), Methods (equations). Light and dark themes, phone width.

## 13. Parity

`tests/test_parity.py`: PyTorch vs ONNX Runtime on fixtures (max abs diff below tolerance);
Playwright test loads the dashboard in in-browser mode on fixture images and compares boxes, strings
and probabilities with `results/parity_fixtures.json` produced by the Python pipeline.

## 14. Quality and developer experience

`uv` with Python 3.12, `ruff`, `mypy --strict` on `plate_reader` and `services`, `pytest` +
`hypothesis`, coverage gate 85% on `plate_reader`; `pre-commit` (ruff, mypy, a check that the repo
never mentions the original dataset host, a check that `data/` holds no real files); `justfile`
recipes: `setup`, `synth`, `eval`, `train-crnn`, `export`, `api`, `worker`, `dashboard`, `check`,
`demo` (synthetic data → eval → compose up); GitHub Actions: lint, type, unit, synthetic eval (small),
ONNX export and parity, dashboard build and tests, Playwright parity, Docker build; CHANGELOG; ADRs;
model card; data card; `docs/insert_your_own_data.md`.

## 15. Facts about the current code (measured 2026-10-18)

Public repo at D:\detectionx5 (2 commits, AGPL-3.0). Packages: `plate_reader` (detector.py 127 lines,
normalize.py 164, ocr.py 159, pipeline.py 258, preprocess.py 109, segment.py 238), `api.py` (FastAPI,
`GET /health`, `POST /read`, 1–10 photos, 10 MiB each, lifespan-loaded models, inference lock),
`cli.py`, `gui.py` (ttkbootstrap). Tests: 24 (api 12, api_sample 1, normalize 6, segment 5) with fake
models. `models/best.pt` is YOLOv10n (one class `LP`, 100 epochs, imgsz 640, batch 16); the shipped
checkpoint is epoch 90 with validation precision 0.956, recall 0.945, mAP@50 0.983, mAP@50-95 0.744;
the README currently shows the final-epoch row (0.958 / 0.957 / 0.987 / 0.743) and must be fixed by
rendering from `docs/training_results.csv`. The README states OCR accuracy is not benchmarked; keep
that statement until a real labelled set exists. The current vote weights each reading's votes by
detector confidence (`pipeline.py` around line 200). The `.venv` has CPU-only torch 2.14 and
ultralytics 8.4; the machine has an RTX 3050 4 GB for which CUDA torch should be installed in the
project environment.

## 16. Glossary

View: one photo or one thresholding variant of a crop. Hypothesis: a candidate string with a
log-probability. Prediction set: the strings kept by conformal prediction at level 1 − α.
Pseudo-real: heavily augmented synthetic data standing in for real photos until they exist.
