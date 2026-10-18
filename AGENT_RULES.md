# Agent rules for the DetectionX5 platform rebuild

These rules bind every agent session in this repository. Read `ARCHITECTURE.md` and `MILESTONES.md`
first. When a rule and convenience conflict, the rule wins. When a rule and the architecture
conflict, write an ADR and stop for review.

## 1. Data (non-negotiable)

1. `data/` is a placeholder until the final step. It holds a README, the folder layout, a validator
   and nothing else. Real images, crops, labels and videos are gitignored; a pre-commit check fails
   if any image or CSV with more than 50 rows is staged under `data/`.
2. Never mention, link or hint at the hosting service or the name of the original training dataset.
   A pre-commit check and a CI test grep the repository for that service's name and fail on a match.
   Describe the detector's training data only as "a plate dataset plus photos from the firm's experts".
3. Every metric computed on synthetic or pseudo-real data is labelled as such in JSON, docs, the
   dashboard and the README, with the sentence "synthetic results are not real-world accuracy".
   The statement "OCR accuracy is not benchmarked on real data" stays until a real labelled set exists.
4. The existing `samples/car.jpg` may stay. Do not add new photographs of real vehicles.

## 2. Honesty

1. No number is typed by hand in any document. Metrics render from `results/*.json` and
   `docs/training_results.csv` through a render step; CI fails on drift or on a hand-typed number in
   governed sections.
2. Every metric carries its set (synthetic, pseudo-real, data), n, a bootstrap CI and the model version.
3. Confidence is calibrated or it is not called confidence. Prediction sets come from conformal
   prediction with the level stated.
4. If a model is not trained, a test is skipped, or a feature is stubbed, PROGRESS.md says so in
   plain words. Never fake a result, a metric, a screenshot or a passing test.
5. The README keeps a limitations section that is at least as honest as the current one.

## 3. Engineering standards

1. Python 3.12 managed by `uv` (`uv python install 3.12`; `.python-version`; `uv sync`); all
   commands run as `uv run …`; dependencies in `pyproject.toml` with lower bounds, locked in `uv.lock`.
   Keep `requirements.txt` generated from the lock for readers who do not use uv.
2. Typed code: `mypy --strict` on `plate_reader/` and `services/`; `ruff` format and lint clean.
   Pydantic v2 at boundaries; `pydantic-settings` for configuration (keep the `PLATE_*` environment
   variable names already in `config.py`); `typer` for the CLI; `structlog` for logging.
3. Tests first for pure functions. `pytest` + `hypothesis`; fixtures are synthetic; model-dependent
   tests use fake models as the existing API tests do, plus a small marked GPU/CPU training smoke test.
   Coverage gate 85% on `plate_reader/`.
4. Deterministic seeds everywhere; byte-identical synthetic images for a seed.
5. The grammar automaton is the single definition of plate formats; no other module may hard-code
   a plate regex.
6. Dashboard: TypeScript strict, ESLint + Prettier, components in Storybook, design tokens, keyboard
   accessible, axe clean, works at phone width. In-browser mode must degrade gracefully when WebGPU
   is unavailable (WASM fallback).
7. Keep `cli.py`, `gui.py` and `api.py` as thin, working shims so existing instructions in the README
   remain true until the README is rewritten in the last milestone.
8. Docstrings explain why, not what.

## 4. Git

1. Branch `feat/platform-rebuild`. Small conventional commits, one concern each.
2. Never push, never open a PR. Mohamed decides when anything leaves the machine.
3. Never add co-author or "generated with" lines to commits. Never use `--no-verify`.
4. Binary files: keep each model under 15 MB; check `.gitattributes` before adding any binary; never
   commit datasets, videos, `.venv`, `output/` artefacts or `results/*.html`.

## 5. Workflow

1. Milestones in order (`MILESTONES.md`); a milestone is done when its definition of done passes and
   `just check` is green; append a `PROGRESS.md` entry after each one (commands, pass/fail counts,
   decisions, stubs, open questions).
2. If blocked, record it with what was tried and continue with the next independent item. No more
   than thirty minutes on any single environment problem; fall back as the architecture specifies
   (CPU training on a reduced synthetic set, WASM instead of WebGPU, SQLite instead of Postgres for
   local tests) and write the ADR.
3. Deviations from `ARCHITECTURE.md` require an ADR before the code.
4. Stop and return a report when M4 is complete, or earlier if context is running low.
5. Never modify anything outside this repository except its own virtual environment and
   `~/.cache` style tool caches. Never touch `D:\CV's` or any other repository.

## 6. Definition of done for the whole rebuild

On a clean clone with an empty `data/` folder, `just demo` generates synthetic plates, trains a
small CRNN (or loads the committed one), runs the evaluation harness with CIs, exports ONNX, passes
parity tests, and brings up API, worker, Redis, Postgres, dashboard and observability in Compose;
CI is green; the README's numbers render from results; `docs/insert_your_own_data.md` explains
exactly where real photos and labels go and what changes once they exist.
