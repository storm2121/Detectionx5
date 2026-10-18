# DetectionX5 task runner. Every Python command runs through uv (AGENT_RULES §3.1).
# Recipes use only commands that behave the same in sh and PowerShell.

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

export UV_LINK_MODE := "copy"
export PYTHONUTF8 := "1"

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

# The gate every milestone must pass.
check: lint type guards
    uv run pytest -q --cov=plate_reader --cov-report=term --cov-fail-under=85
    uv run plate docs check
    uv run plate data validate
