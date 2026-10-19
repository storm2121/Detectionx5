# DetectionX5 task runner. Every Python command runs through uv (AGENT_RULES §3.1).
# Recipes use only commands that behave the same in sh and PowerShell.

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

export UV_LINK_MODE := "copy"
export PYTHONUTF8 := "1"
export COREPACK_ENABLE_DOWNLOAD_PROMPT := "0"

# The dashboard's package manager, run through Node's corepack (no global install).
pnpm := "corepack pnpm@9.15.9 --dir apps/dashboard"

# Host ports, chosen to avoid clashes with other projects on the same machine.
export PLATE_API_PORT := "8100"

default:
    @just --list

# Create .venv (Python 3.12, every dependency group) and install the git hooks.
setup:
    uv sync
    uv run pre-commit install --install-hooks

# Re-lock and regenerate the pip requirement files from the lock.
lock:
    uv lock
    uv export --format requirements-txt --no-hashes --no-dev --emit-index-url --quiet -o requirements.txt
    uv export --format requirements-txt --no-hashes --all-groups --emit-index-url --quiet -o requirements-dev.txt

fmt:
    uv run ruff format .
    uv run ruff check --fix .

lint:
    uv run ruff format --check .
    uv run ruff check .

type:
    uv run mypy plate_reader services

guards:
    uv run python tools/repo_guards.py names --all
    uv run python tools/repo_guards.py data --all

test *args:
    uv run pytest {{args}}

# Render README and docs numbers from docs/training_results.csv and results/*.json.
docs:
    uv run plate docs render

# Deterministic synthetic sets under synthetic/ (gitignored); equal seeds give equal bytes.
synth n="1000" seed="0":
    uv run plate synth crops --n {{n}} --seed {{seed}}
    uv run plate synth pseudo-real --n {{n}} --seed {{seed}}
    uv run plate synth views --n 200 --k 5 --seed {{seed}}
    uv run plate synth scenes --n 200 --seed {{seed}}

# Evaluate on the synthetic set (with multi-view fusion) and re-render the README.
eval *args:
    uv run plate eval --set synthetic {{args}}
    uv run plate docs render

# Train the CRNN on synthetic crops (CUDA when available), export ONNX, calibrate.
train-crnn *args:
    uv run plate train crnn {{args}}

# Export the CRNN and the detector to ONNX and rewrite the parity fixtures.
export:
    uv run plate export onnx
    uv run plate export detector
    uv run plate export fixtures

# The platform service on host port 8100 (SQLite under storage/ unless PLATE_DB_URL is set).
api:
    uv run uvicorn services.api.main:app --host 127.0.0.1 --port {{PLATE_API_PORT}}

# A job worker (needs Redis; Compose maps it to host port 6380).
worker:
    uv run python -m services.api.worker

# The Vue console on http://localhost:5174 (Vite; /api is proxied to the service on 8100).
dashboard:
    {{pnpm}} install --frozen-lockfile
    {{pnpm}} dev

# Dashboard lint, type check and build, unit tests and the Storybook build.
dashboard-check:
    {{pnpm}} install --frozen-lockfile
    {{pnpm}} lint
    {{pnpm}} build
    {{pnpm}} test
    {{pnpm}} storybook:build

# Playwright smoke and axe checks against the running stack (`docker compose up` first).
dashboard-e2e:
    {{pnpm}} exec playwright install chromium
    {{pnpm}} e2e

# Synthetic data, a small evaluation, then the whole stack in Compose and a synthetic read
# of three photos of one car; the console is then on http://localhost:5174.
demo:
    uv run plate synth crops --n 200 --seed 0
    uv run plate eval --set synthetic --n 50 --views 20 -r crnn-greedy -r crnn-beam --out .cache/demo-results --quiet
    docker compose up --build -d --wait
    uv run python tools/demo_read.py

# The gate every milestone must pass.
check: lint type guards dashboard-check
    uv run pytest -q --cov=plate_reader --cov-report=term --cov-fail-under=85
    uv run plate docs check
    uv run plate data validate
