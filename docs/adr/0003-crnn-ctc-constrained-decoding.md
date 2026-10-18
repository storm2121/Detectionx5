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

## As built (M2)

- Network: channels `(32, 64, 128, 160)` over four residual stages, a two-layer BiLSTM with
  hidden size `128`, input `32 x 160`, `40` time steps; about one and a half million
  parameters, so `models/crnn.onnx` and `models/crnn.pt` stay far under the 15 MB limit.
- Training (`plate train crnn`): crops generated on the fly in DataLoader workers, every
  epoch a fresh slice of the stream; AdamW with a one-cycle schedule; fp16 autocast on CUDA
  with the CTC loss in fp32; a curriculum that raises the strength bound from `0.3` to `1`
  over the first 60 per cent of the epochs; the kept epoch is the best by greedy exact match
  on the synthetic validation split. GPU training is seeded but not bitwise reproducible
  (cuDNN LSTM kernels), so the model's version is the hash of its ONNX bytes.
- Export: the TorchScript-based exporter (`dynamo=False`), because the dynamo exporter of
  torch 2.14 only targets opset 18 and above; the graph uses the native ONNX `LSTM` op.
- Calibration (`plate train calibrate`): the temperature is fitted by golden-section search
  on `log T`, minimising the NLL of the true plate under the beam posterior that inference
  reports (not the per-frame CTC loss), on the `calibration` split; conformal thresholds
  come from the `conformal` split and coverage is measured on the `test` split. All three are
  disjoint synthetic splits with fixed seeds.
- Parity: `tests/test_parity.py` checks a random-weight export at batch sizes one and four,
  the committed ONNX against the committed PyTorch weights, and `results/parity_fixtures.json`
  (sixteen synthetic fixture PNGs under `tests/fixtures/parity/`, written by
  `plate export fixtures`), which the browser runtime must also reproduce.

## Consequences

PyTorch becomes a real dependency for training (the `ml` group); the browser mode becomes
possible; the harness can show the sim-to-real gap. Training on CPU is slow, so a reduced
synthetic run is the documented fallback.
