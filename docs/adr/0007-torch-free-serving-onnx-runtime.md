# ADR 0007: torch-free serving through ONNX Runtime

Status: accepted (executing agent, 2026-10-18). Refines ARCHITECTURE.md §10 and §11,
which do not fix the serving runtime.

## Context

PyTorch, Ultralytics and EasyOCR together add well over a gigabyte to a container image
and dominate start-up time. The service and the worker only need inference. The
architecture already requires ONNX exports of the detector and the CRNN (for the browser,
ARCHITECTURE §12 and §13) and parity tests between PyTorch and ONNX Runtime.

## Decision

- Runtime dependencies of the package (`[project.dependencies]`) are torch-free: numpy,
  OpenCV (headless), ONNX Runtime, FastAPI, SQLAlchemy, RQ, OpenTelemetry and friends.
- PyTorch, torchvision, Ultralytics, EasyOCR and ONNX tooling live in the `ml` dependency
  group, used for training, export and the EasyOCR baseline; the desktop GUI dependency
  lives in the `gui` group. Both are default groups for `uv sync`, so a development
  checkout has everything; container images install `--no-default-groups`.
- The service and the worker run the CRNN, and the detector when its ONNX export exists,
  through ONNX Runtime; decoding, calibration and fusion are numpy code shared with the
  evaluation harness. The PyTorch detector path (`PlateDetector`) remains for the CLI,
  GUI and legacy API.

## Consequences

Small images and fast cold starts; one more reason the parity tests matter, since the
service never runs the PyTorch graph. Any feature that needs EasyOCR in the service must
install the `ml` group explicitly.
