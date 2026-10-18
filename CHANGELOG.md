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

### Changed

- M0: the README detector table now shows the shipped checkpoint (epoch 90) instead of
  the final epoch; it is rendered, not typed.
- M0: `normalize.py` parses through the grammar automaton instead of regexes; temporary
  plates accept 1 to 6 digits as the architecture specifies (previously 5 or 6).
- M0: configuration is typed with pydantic-settings; `config.py` remains as a shim with
  the same names and `PLATE_*` variables.

### Removed

- M0: the credits line naming the detector's original training-data source; the README
  now describes it as a plate dataset plus photos from the firm's experts.
