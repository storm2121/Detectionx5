# ADR 0003: a CRNN with CTC and grammar-constrained beam search beside the EasyOCR path

Status: accepted (architect, 2026-10-18). Expand during M2.

## Context

The current recogniser is two EasyOCR models with restricted alphabets reading segmented fields.
It returns strings with heuristic scores, cannot be exported to the browser, and its accuracy is not
measured. The platform needs per-timestep posteriors for fusion, calibration and conformal sets.

## Decision

Train a compact CRNN (CNN + BiLSTM + CTC) in PyTorch on synthetic crops, fine-tunable on real crops,
decoded with a prefix beam search pruned by the grammar automaton, calibrated by temperature scaling,
exported to ONNX. The EasyOCR path stays as the baseline and both are reported by the harness.

## Consequences

PyTorch becomes a real dependency and a real skill; the browser mode becomes possible; the harness
can show the sim-to-real gap. Training on CPU is slow, so a reduced synthetic run is the fallback.
