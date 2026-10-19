# CV notes

The lines below are the ones the milestones asked for, each traced to the code, tests and
results that back it, so a reader can check every claim. The figures in the last section are
rendered from `results/*.json` by `uv run plate docs render`; nothing here is typed by hand,
and synthetic results are not real-world accuracy.

## Lines and their evidence

- **Synthetic-first data and evaluation.** "Built a byte-deterministic synthetic plate
  generator and an evaluation harness with paired bootstrap intervals, so a recogniser with
  no labelled real data is still measured honestly."
  Code: `plate_reader/synthetic/`, `plate_reader/eval/`. Tests: `tests/test_synthetic.py`
  (byte-identical PNGs for a seed, grammar-valid labels), `tests/test_eval.py`. CI: the
  determinism step and the small synthetic evaluation. Results:
  `results/eval_synthetic.json`, `results/eval_pseudo_real.json`.
- **A grammar-constrained CRNN.** "Trained a CRNN with CTC and a beam search constrained by
  the plate grammar, compiled to a minimal automaton, and served it through ONNX Runtime."
  Code: `plate_reader/grammar.py`, `plate_reader/crnn/`, `plate_reader/training/`. Tests:
  `tests/test_grammar.py`, `tests/test_crnn_decode.py`, `tests/test_parity.py` (PyTorch
  against ONNX). Results: `results/train_crnn.json`, `results/eval_synthetic.json`.
- **Calibrated confidence and conformal sets.** "Calibrated the recogniser with temperature
  scaling on the reported posterior and wrapped every read in split-conformal prediction
  sets, one threshold per number of fused views, with coverage checked by a joint
  bootstrap." Code: `plate_reader/crnn/calibrate.py`, `plate_reader/crnn/conformal.py`,
  `plate_reader/training/calibrate_fused.py`. Tests: `tests/test_training.py`. Results:
  `results/calibration_crnn.json`, `results/calibration_fused.json`.
- **Multi-view fusion.** "Fused several photos of one car in probability space, with
  per-character posteriors and property tests for permutation invariance, single-view
  consistency and monotonicity." Code: `plate_reader/fusion.py`. Tests:
  `tests/test_fusion.py` (hypothesis). Method: `docs/methods/fusion.md`. Results:
  `results/eval_views.json`.
- **A reviewable service.** "Built the plate service (FastAPI, PostgreSQL, RQ on Redis) with
  a review queue whose corrections export as training data, background video jobs with
  tracking, and OpenTelemetry traces and Prometheus metrics in Grafana and Tempo." Code:
  `services/api/`, `docker-compose.yml`, `docker/`. Tests: `tests/test_service.py`,
  `tests/test_tracking_registry.py`. Verified end to end: `PROGRESS.md`, M4 and M5.
- **The console.** "Designed a Vue 3 and TypeScript console for the reader with D3
  calibration and confusion views, a review queue and a character-level confidence
  heatmap." Code: `apps/dashboard/`. Tests: the Vitest suite in `apps/dashboard/src`,
  Storybook stories, and `apps/dashboard/e2e/smoke.spec.ts` (Playwright with axe on every
  page, both themes, desktop and phone width, against Compose).
- **In-browser inference with parity.** "Ran the detector and recogniser in the browser
  through ONNX Runtime Web with CI parity tests against the Python pipeline, so no photo has
  to leave the device." Code: `apps/dashboard/src/inference/` (TypeScript ports of OpenCV's
  colour conversion and resizing, the letterbox, the constrained beam and the fusion).
  Tests: `apps/dashboard/src/inference/__tests__/` (byte-exact against
  `tests/fixtures/web/opencv_cases.json`), `apps/dashboard/e2e/parity.spec.ts` (every
  fixture of `results/parity_fixtures.json` within its stated tolerance, in CI).
- **Domain randomisation.** "Searched augmentation strengths with Optuna against a
  pseudo-real tuning split, with paired bootstrap differences between trials." Code:
  `plate_reader/training/sweep.py`. Tests: `tests/test_sweep.py`. Results:
  `results/sweep.json`, rendered in `docs/model_card.md`.
- **Engineering hygiene.** "Kept every documented number rendered from its source and
  checked in CI, with mypy --strict, a coverage gate, repository guards and ADRs." Code:
  `plate_reader/docs_render.py`, `tools/repo_guards.py`, `.github/workflows/ci.yml`,
  `docs/adr/`. Tests: `tests/test_docs_render.py`, `tests/test_repo_guards.py`.

## The figures

<!-- BEGIN RENDER cv-evidence -->
**Synthetic results are not real-world accuracy.** Values with 95% bootstrap intervals where the source records one.

| Claim | Value | Source |
|---|---|---|
| CRNN (constrained beam), exact match on the synthetic test set | 0.990 [0.980, 1.000] | `results/eval_synthetic.json` |
| EasyOCR baseline, exact match on the same set | 0.353 [0.297, 0.407] | `results/eval_synthetic.json` |
| CRNN (constrained beam), expected calibration error | 0.009 [0.002, 0.017] | `results/eval_synthetic.json` |
| CRNN, exact match of the probabilistic fusion of 5 views | 1.000 [1.000, 1.000] | `results/eval_synthetic.json` |
| Conformal sets at level 0.95, measured coverage | 0.955 [0.935, 0.965] | `results/calibration_crnn.json` |
| Conformal sets at level 0.90, measured coverage | 0.901 [0.882, 0.918] | `results/calibration_crnn.json` |
| Fused sets over 5 views at level 0.95, measured coverage | 0.940 [0.905, 0.970] | `results/calibration_fused.json` |
| CRNN (constrained beam), exact match on the pseudo-real set | 0.610 [0.553, 0.660] | `results/eval_pseudo_real.json` |
| Augmentation sweep, best of 8 trials on the pseudo-real tuning split | 0.726 | `results/sweep.json` |
| Detector mAP@50 and mAP@50-95 on synthetic street scenes (one pass, no interval) | 0.843 and 0.602 | `results/eval_detector_synthetic.json` |
| CRNN parameters | 1440051 | `results/train_crnn.json` |
<!-- END RENDER cv-evidence -->

## What not to claim

- Any real-world accuracy: there is no labelled real evaluation set yet.
- That the detector's real-photo figures are independent: they come from its own
  validation split. Its only independent figures are on synthetic street scenes.
- That the augmentation sweep improved the shipped model: its best configuration has not
  been used for a full training.
