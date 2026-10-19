# ADR 0008: the Python environment (uv, Python 3.12, CUDA 12.6 PyTorch, headless OpenCV)

Status: accepted (executing agent, 2026-10-18).

## Context

The previous `.venv` held Python 3.11, CPU-only torch, `numpy<2` and both
`opencv-python` and `opencv-python-headless` (which overwrite each other's `cv2`). The
development machine has a 4 GB laptop GPU whose driver reports CUDA 12.4.

## Decision

- `uv` manages Python 3.12 (`.python-version`, `requires-python = "==3.12.*"`); the lock is
  universal but restricted to Windows and Linux, the two supported platforms.
- PyTorch and torchvision come from the PyTorch wheel indexes through `[tool.uv.sources]`
  with platform markers: CUDA 12.6 builds on Windows, CPU builds on Linux (CI and
  containers). The newest CUDA 12.4 builds stop at torch 2.6, so cu126 is used; it runs on
  the 12.4 driver through CUDA minor-version compatibility. Verified on this machine:
  `torch 2.14.1+cu126` sees the GPU and runs convolution and LSTM forward and backward.
- `opencv-python` is removed from the resolution with an override (Ultralytics asks for it,
  EasyOCR asks for the headless build); only `opencv-python-headless` is installed.
- `numpy` 2 is allowed; the old `numpy<2` pin existed for a mixed binary stack that the lock
  no longer produces.
- `requirements.txt` and `requirements-dev.txt` are generated from the lock (`just lock`)
  for readers who do not use uv; they carry the PyTorch index URLs and platform markers.

## Consequences

`uv sync` gives a GPU-capable environment on the development machine and a CPU one in CI
and containers from the same lock. macOS is not in the lock; macOS users can install from
`requirements.txt` with a CPU torch.
