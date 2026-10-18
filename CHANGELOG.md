# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- M0: `uv` project on Python 3.12 (`pyproject.toml`, `uv.lock`, `.python-version`) with
  CUDA 12.6 PyTorch on Windows and CPU PyTorch on Linux; `requirements*.txt` generated
  from the lock.
- M0: `plate_reader/grammar.py`, the plate formats compiled into one minimal DFA, with
  hypothesis property tests.
- M0: the `plate` command line (`read`, `data validate`, `data init`, `docs render`,
  `docs check`, `version`).
- M0: the `data/` placeholder layout, `data/README.md`, `plate data validate` and
  `docs/insert_your_own_data.md`.
- M0: README numbers rendered from `docs/training_results.csv` and `results/*.json`;
  `plate docs check` fails on drift and on hand-typed metric-like numbers.
- M0: repository guards (no dataset-host mention, no real data under `data/`) as
  pre-commit hooks and CI tests; `justfile`; `.editorconfig`; CI workflow; ADRs 0001 to
  0008.

- M1: `plate_reader/synthetic/`, a byte-deterministic generator of plate crops, scenes,
  multi-view sets and a pseudo-real set, with bundled OFL fonts and documented augmentation
  distributions; `plate synth crops|scenes|views|pseudo-real`.
- M1: `plate_reader/eval/`, the evaluation harness: exact match, per-field accuracy, CER,
  read rate, ECE and reliability bins, letter confusion, latency percentiles, paired
  bootstrap intervals, multi-view fusion at 1, 3 and 5 views, an HTML report and a
  content-addressed read cache; `plate eval --set synthetic|pseudo_real|data|views`.
- M1: `results/eval_synthetic.json` (the EasyOCR path and the legacy vote on synthetic
  plates) rendered into the README with the synthetic label; CI runs a small synthetic
  evaluation and a byte-determinism check.

- M2: `plate_reader/crnn/`: CRNN (residual CNN, BiLSTM, CTC), numpy decoders (greedy,
  prefix beam, grammar-constrained prefix beam), temperature scaling fitted on the reported
  posterior, split conformal prediction sets with a joint-bootstrap coverage interval, and
  an ONNX Runtime wrapper with metadata (`models/crnn.json`).
- M2: `plate train crnn` (synthetic pretraining with a curriculum, optional fine-tuning on
  `data/ocr`), `plate train calibrate`, `plate export onnx`, `plate export fixtures`; the
  trained `models/crnn.onnx` and `models/crnn.pt`; PyTorch-versus-ONNX parity tests.
- M2: the harness compares the EasyOCR path with CRNN greedy, constrained beam and
  unconstrained beam on the synthetic and pseudo-real sets; model card v1.

- M3: probabilistic multi-view fusion (`plate_reader/fusion.py`) with per-position
  character posteriors from Levenshtein alignment, optional quality weights and fused
  conformal sets; hypothesis property tests (permutation invariance, single-view
  consistency, monotonicity in weights); `docs/methods/fusion.md` with the equations;
  `results/eval_views.json` compares the legacy vote with probabilistic fusion at 1, 3 and 5
  views.

### Changed

- M3: `plate_reader.pipeline.PlatePipeline` (detect, read, fuse, conformal set) fuses
  probabilistically by default; `read_images`, `plate read` and `cli.py` take
  `--fusion auto|probabilistic|vote`, where `auto` uses the product only for calibrated views
  and otherwise the original vote (ADR 0009).

- M0: the README detector table now shows the shipped checkpoint (epoch 90) instead of
  the final epoch; it is rendered, not typed.
- M0: `normalize.py` parses through the grammar automaton instead of regexes; temporary
  plates accept 1 to 6 digits as the architecture specifies (previously 5 or 6).
- M0: configuration is typed with pydantic-settings; `config.py` remains as a shim with
  the same names and `PLATE_*` variables.

### Removed

- M0: the credits line naming the detector's original training-data source; the README
  now describes it as a plate dataset plus photos from the firm's experts.
