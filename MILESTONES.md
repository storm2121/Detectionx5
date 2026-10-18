# Milestones

Each milestone ends with its definition of done (DoD) passing and `just check` green, then a
`PROGRESS.md` entry. CV lines use `{n}` placeholders filled only from `results/*.json`.

## M0. Scaffold, guard rails, data placeholder, honest README numbers

- `uv` project on Python 3.12 (`pyproject.toml`, `uv.lock`, `.python-version`, generated
  `requirements.txt`), `justfile`, `.pre-commit-config.yaml` (ruff, mypy, dataset-name check, data
  folder check), `.editorconfig`, `.gitignore`, `CHANGELOG.md`, ADRs 0001–0006 filled from the stubs,
  `.github/workflows/ci.yml` (lint, type, test).
- `plate_reader/grammar.py` with the automaton and hypothesis tests; existing modules typed to pass
  `mypy --strict`; existing 24 tests still green.
- `data/README.md`, the folder layout, `plate data validate`, `docs/insert_your_own_data.md` (first version).
- Render step: `plate docs render` fills README placeholders from `docs/training_results.csv`
  (epoch 90 row) and `results/*.json`; `plate docs check` fails on drift; the wrong final-epoch table
  is gone; a test proves a hand-typed number fails the check.
- DoD: `uv run plate --help`, `uv run pytest`, `uv run mypy plate_reader services`,
  `pre-commit run --all-files`, `uv run plate docs check` all pass; grep for the dataset host name
  returns nothing.
- CV line: none yet.

## M1. Synthetic plates and the evaluation harness

- `plate_reader/synthetic/` per ARCHITECTURE §6 with bundled OFL fonts and hypothesis invariants;
  `plate synth crops|scenes|views|pseudo-real --out … --n … --seed …`.
- `plate_reader/eval/` per §9; `plate eval --set synthetic` evaluates the existing EasyOCR path and
  the legacy vote; HTML report; `results/eval_synthetic.json`; CI runs a small synthetic evaluation.
- DoD: `plate synth` is byte-deterministic; `plate eval --set synthetic` writes JSON with bootstrap
  CIs; the README renders the synthetic baseline with the synthetic label; CI green.
- CV line: "Built a synthetic Moroccan-plate generator (perspective, blur, occlusion, two formats)
  and an evaluation harness reporting exact-match, per-field accuracy and character error rate with
  bootstrap intervals, so the pipeline is measurable before any real data exists."

## M2. CRNN recogniser, constrained decoding, calibration, conformal sets, ONNX

- `plate_reader/crnn/` per §7; `plate train crnn` on synthetic crops (GPU if CUDA torch installs,
  else a reduced CPU run documented in PROGRESS); grammar-constrained prefix beam search; temperature
  scaling; conformal prediction with coverage report; `plate export onnx`; PyTorch-vs-ONNX parity test.
- Harness compares EasyOCR path vs CRNN greedy vs CRNN constrained beam on synthetic and pseudo-real.
- DoD: a committed `models/crnn.onnx` under 15 MB; `results/eval_synthetic.json` holds all three
  recognisers; conformal coverage at α = 0.1 is within its CI of 0.9 on the synthetic calibration
  split; parity test green; model card v1.
- CV line: "Trained a CRNN with CTC loss on synthetic plates and decoded it with a grammar-constrained
  beam search, calibrated by temperature scaling and wrapped in conformal prediction sets with
  {n} coverage at the 90% level."

## M3. Multi-view probabilistic fusion

- `plate_reader/fusion.py` per §8 with hypothesis property tests; per-position posteriors;
  `docs/methods/fusion.md` with the equations; harness reports legacy vote vs probabilistic fusion on
  multi-view synthetic sets (K = 1, 3, 5 views).
- DoD: property tests green; `results/eval_views.json` shows both methods with CIs; the pipeline uses
  probabilistic fusion by default with the legacy vote selectable.
- Note (accepted 2026-10-18, ADR 0009): met in spirit. `PlatePipeline`, the calibrated CRNN path
  the service uses, fuses probabilistically by default; the EasyOCR `read_images` path defaults to
  `auto`, which keeps the vote because EasyOCR's vote shares are not calibrated and the vote
  measured better for them. Both methods stay selectable.
- CV line: "Replaced string voting with grammar-constrained probabilistic fusion across photos,
  combining per-view CTC posteriors into a plate posterior with per-character confidence."

## M4. Read log, review queue, active learning, jobs, observability, Compose

- `services/api` per §11: Postgres schema with Alembic (SQLite fallback), review policy, export of
  corrections to `data/ocr/train`, `plate registry promote`, RQ worker on Redis for folders and video
  with IoU tracking, SSE progress, OpenTelemetry spans, Prometheus metrics, Grafana dashboard JSON;
  Dockerfiles and `docker-compose.yml` for api, worker, redis, postgres, otel-collector, prometheus,
  grafana (dashboard placeholder service).
- DoD: API tests with fake models cover every endpoint; a review round-trip test (read → queue →
  correction → export → file appears under `data/ocr/train`); `docker compose up` serves `/health`
  and a synthetic read; metrics visible at `/metrics`.
- CV line: "Shipped the reader as a FastAPI service with a PostgreSQL review queue that exports
  corrections for retraining, Redis-backed batch and video jobs with live progress, and
  OpenTelemetry tracing into Grafana."
- **Stop here and report** (AGENT_RULES §5.4), unless context allows continuing safely.

## M5. Vue dashboard

- `apps/dashboard` per §12 with all pages, server mode first; Storybook, Vitest, Playwright smoke,
  axe checks; themes; phone width.
- DoD: `pnpm build`, `pnpm test`, `pnpm storybook:build` and Playwright smoke against Compose pass;
  the Read page shows boxes, fields, hypotheses, the conformal set and the character heatmap.
- CV line: "Designed a Vue 3 and TypeScript console for the reader with D3 calibration and
  confusion views, a review queue and a character-level confidence heatmap."

## M6. In-browser inference, parity, sim-to-real page, domain-randomisation sweep

- onnxruntime-web mode (WASM, WebGPU when available) running detector and CRNN in the browser with
  TypeScript pre- and post-processing; Playwright parity test against `results/parity_fixtures.json`;
  the Models page shows the sim-to-real gap (synthetic vs pseudo-real now, vs real once data exists);
  `plate sweep` runs an Optuna search over augmentation strengths against the pseudo-real set.
- DoD: parity within tolerance in CI; sweep writes `results/sweep.json`; dashboard mode toggle works
  with a parity indicator.
- CV line: "Ran the detector and recogniser in the browser through ONNX Runtime Web with CI parity
  tests against the Python pipeline, so no photo has to leave the device."

## M7. Documentation and demo

- README rewrite (what, why, how; architecture diagram; rendered numbers; honesty and limitations;
  insert-your-own-data; what changes once real data arrives), model card, data card, CHANGELOG,
  ADRs complete, `docs/CV_NOTES.md`, `just demo` verified on a clean clone with empty `data/`.
- DoD: clean-clone demo passes; CI green; `plate docs check` green; no dataset host name anywhere.
- CV line: assembled from `docs/CV_NOTES.md`.
