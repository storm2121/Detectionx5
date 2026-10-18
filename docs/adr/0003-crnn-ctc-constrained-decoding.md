# ADR 0003: a CRNN with CTC and grammar-constrained beam search beside the EasyOCR path

Status: accepted (architect, 2026-10-18); expanded during M0 and M2 by the executing agent.

## Context

The current recogniser is two EasyOCR models with restricted alphabets reading segmented
fields. It returns strings with heuristic scores, cannot be exported to the browser, and
its accuracy is not measured. The platform needs per-timestep posteriors for fusion,
calibration and conformal sets.

## Decision

- A compact CRNN in PyTorch: residual CNN blocks with height-collapsing pooling, a
  two-layer bidirectional LSTM and a linear CTC head over the grammar's `SYMBOLS` with the
  blank at index 0. Trained on synthetic crops generated on the fly (deterministic by
  seed and sample index) with a curriculum over augmentation strength; fine-tunable on
  `data/ocr` when present; mixed precision on CUDA, CPU fallback.
- Decoders: greedy (best path), CTC prefix beam search, and grammar-constrained prefix
  beam search in which the automaton of ADR 0001 prunes every extension that cannot lead
  to a plate and only accepting prefixes survive the final step. Beams keep the top-k
  strings with log-probabilities. Decoders run in numpy so the torch-free service
  (ADR 0007) and the parity tests use the same code.
- Calibration: temperature scaling of the logits, fitted on a held-out synthetic split.
- Export: ONNX, opset 17, dynamic batch, logits as the output; temperature and decoding
  stay outside the graph so every runtime applies the same post-processing. A parity test
  compares PyTorch and ONNX Runtime outputs on fixtures.
- The EasyOCR path stays as the baseline and the harness reports both.

## Consequences

PyTorch becomes a real dependency for training (the `ml` group); the browser mode becomes
possible; the harness can show the sim-to-real gap. Training on CPU is slow, so a reduced
synthetic run is the documented fallback.
