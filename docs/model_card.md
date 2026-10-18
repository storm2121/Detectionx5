# Model card: CRNN plate recogniser

Status: v1 (milestone M2). Every number on this page is rendered by `uv run plate docs render`
from `results/train_crnn.json`, `results/calibration_crnn.json` and `results/eval_*.json`;
`uv run plate docs check` fails if one is edited by hand. Synthetic results are not
real-world accuracy.

## Model details

- Architecture: a residual CNN (four stages of two `3 x 3` convolutions with batch norm),
  max pooling that halves the width twice and collapses the height, a mean over what is
  left of the height axis, a two-layer bidirectional LSTM, and a linear CTC head. The
  classes are the CTC blank followed by the grammar's symbols in `plate_reader/grammar.py`
  order (ten digits, the six letters `أ ب د ه و ط`, `W`, the separator).
- Input: one grey channel, `32 x 160`, OpenCV grey weights, scaled to `[-1, 1]`
  (`plate_reader/crnn/preprocess.py` is the contract every runtime implements).
- Output: raw logits per time step. Temperature, softmax and decoding are applied outside
  the graph so PyTorch, ONNX Runtime and the browser share them.
- Decoding: grammar-constrained CTC prefix beam search; the automaton prunes every
  extension that cannot become a plate, so every returned string is a valid plate. Greedy
  and unconstrained beam decoding are kept as ablations.
- Confidence: the beam renormalised over its grammar-valid strings at the fitted
  temperature, i.e. the model's posterior conditioned on the output being a plate.
- Prediction sets: split conformal prediction at the levels in `models/crnn.json`.
- Files: `models/crnn.onnx` (opset 17, dynamic batch), `models/crnn.json` (charset
  fingerprint, input contract, temperature, beam width, conformal thresholds),
  `models/crnn.pt` (PyTorch weights, for the parity test and for fine-tuning).
- Version: the first twelve hexadecimal digits of the ONNX file's SHA-256.

<!-- BEGIN RENDER crnn-training -->
`models/crnn.onnx` (version `5348143705d4`, 5.8 MB, 1440051 parameters): trained on synthetic crops only, 24 epochs of 20000 freshly generated crops each on `cuda`, in 1139.4 s. The kept epoch is 18, chosen by greedy exact match on the synthetic validation split (0.995). Fine-tuned on real data: no. Synthetic results are not real-world accuracy.
<!-- END RENDER crnn-training -->

## Intended use

Reading Moroccan civilian plates (standard and temporary `WW`) from detector crops inside
this platform, with calibrated confidence and a prediction set that route uncertain reads
to a human review queue. It is not meant to make unreviewed decisions about people.

## Training data

Synthetic crops only, generated on the fly by `plate_reader/synthetic/` from the `train`
split seed in `plate_reader/synthetic/splits.py`, with a curriculum that raises the
augmentation strength over the first part of training. No real photograph was used. When
labelled crops exist under `data/ocr/train`, `plate train crnn` fine-tunes on them; until
then the model has never seen a real plate.

## Evaluation

Calibration and conformal coverage, on three disjoint synthetic splits:

<!-- BEGIN RENDER crnn-calibration -->
**Synthetic results are not real-world accuracy.** Model `5348143705d4`; temperature fitted on the synthetic calibration split (n = 2000): T = 0.889, NLL of the true plate 0.040 at T = 1 and 0.040 after.

| Split | Exact match | Mean confidence | ECE |
|---|---|---|---|
| calibration, T = 1 | 0.995 [0.992, 0.998] | 0.995 [0.993, 0.996] | 0.004 [0.002, 0.006] |
| calibration, fitted T | 0.995 [0.992, 0.998] | 0.996 [0.994, 0.997] | 0.002 [0.002, 0.006] |
| test, fitted T | 0.995 [0.991, 0.998] | 0.997 [0.995, 0.998] | 0.004 [0.002, 0.007] |

Conformal prediction sets (thresholds from the conformal split, n = 2000; coverage measured on the test split, n = 2000, with a joint bootstrap over both splits):

| Level | Coverage | Mean set size | Singleton sets |
|---|---|---|---|
| 90% | 0.901 [0.882, 0.918] | 0.901 [0.882, 0.918] | 0.901 |
| 95% | 0.955 [0.935, 0.965] | 0.955 [0.935, 0.965] | 0.955 |
<!-- END RENDER crnn-calibration -->

Comparison with the EasyOCR baseline on the synthetic evaluation set:

<!-- BEGIN RENDER synthetic-baseline -->
**Synthetic results are not real-world accuracy.** Set: synthetic (`synthetic`), n = 300, generator seed 1005; values with 95% bootstrap intervals over images (1000 resamples).

| Recogniser | Version | Exact match | Digits | Letter | Region | CER | ECE | Set coverage |
|---|---|---|---|---|---|---|---|---|
| easyocr | `easyocr-1.7.2+segmentation` | 0.353 [0.297, 0.407] | 0.417 [0.357, 0.473] | 0.639 [0.581, 0.696] | 0.522 [0.460, 0.585] | 0.579 [0.525, 0.639] | 0.192 [0.151, 0.235] | n/a |
| crnn-greedy | `crnn-5348143705d4-T0.888664` | 0.990 [0.980, 1.000] | 0.993 [0.983, 1.000] | 0.996 [0.987, 1.000] | 0.996 [0.986, 1.000] | 0.002 [0.000, 0.006] | 0.288 [0.264, 0.310] | n/a |
| crnn-beam | `crnn-5348143705d4-T0.888664` | 0.990 [0.980, 1.000] | 0.993 [0.983, 1.000] | 0.996 [0.987, 1.000] | 0.996 [0.986, 1.000] | 0.002 [0.000, 0.006] | 0.009 [0.002, 0.017] | 0.900 [0.867, 0.933] |
| crnn-beam-unconstrained | `crnn-5348143705d4-T0.888664` | 0.990 [0.980, 1.000] | 0.993 [0.983, 1.000] | 0.996 [0.987, 1.000] | 0.996 [0.986, 1.000] | 0.002 [0.000, 0.006] | 0.009 [0.003, 0.018] | n/a |

Set coverage is the share of truths inside the conformal set at the level fixed on the synthetic conformal split; it holds its level only when the evaluated images are exchangeable with that split, so a drop on the pseudo-real set is the expected warning sign of a distribution shift, not a bug.

Multi-view sets (exact match of the fused read; n = 100 sets, bootstrap over sets):

| Recogniser | Fusion | 1 view(s) | 3 view(s) | 5 view(s) |
|---|---|---|---|---|
| easyocr | legacy_vote | 0.380 [0.290, 0.470] | 0.650 [0.550, 0.740] | 0.650 [0.550, 0.740] |
| easyocr | probabilistic | 0.380 [0.290, 0.470] | 0.580 [0.480, 0.670] | 0.620 [0.530, 0.720] |
| easyocr | probabilistic_weighted | 0.380 [0.290, 0.470] | 0.600 [0.500, 0.690] | 0.640 [0.540, 0.730] |
| crnn-greedy | legacy_vote | 0.980 [0.950, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-greedy | probabilistic | 0.980 [0.950, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-greedy | probabilistic_weighted | 0.980 [0.950, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | legacy_vote | 0.980 [0.950, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | probabilistic | 0.980 [0.950, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | probabilistic_weighted | 0.980 [0.950, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam-unconstrained | legacy_vote | 0.980 [0.950, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam-unconstrained | probabilistic | 0.980 [0.950, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam-unconstrained | probabilistic_weighted | 0.980 [0.950, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
<!-- END RENDER synthetic-baseline -->

On the pseudo-real set (heavier augmentation standing in for the sim-to-real gap):

<!-- BEGIN RENDER pseudo-real-baseline -->
**Synthetic results are not real-world accuracy.** Set: pseudo_real (`pseudo_real`), n = 300, generator seed 1006; values with 95% bootstrap intervals over images (1000 resamples).

| Recogniser | Version | Exact match | Digits | Letter | Region | CER | ECE | Set coverage |
|---|---|---|---|---|---|---|---|---|
| easyocr | `easyocr-1.7.2+segmentation` | 0.023 [0.007, 0.043] | 0.030 [0.013, 0.050] | 0.135 [0.095, 0.181] | 0.021 [0.004, 0.041] | 0.951 [0.930, 0.969] | 0.153 [0.117, 0.193] | n/a |
| crnn-greedy | `crnn-5348143705d4-T0.888664` | 0.600 [0.540, 0.650] | 0.693 [0.640, 0.743] | 0.810 [0.758, 0.861] | 0.696 [0.637, 0.752] | 0.167 [0.138, 0.200] | 0.173 [0.138, 0.216] | n/a |
| crnn-beam | `crnn-5348143705d4-T0.888664` | 0.610 [0.553, 0.660] | 0.717 [0.667, 0.767] | 0.865 [0.823, 0.908] | 0.751 [0.693, 0.804] | 0.164 [0.135, 0.197] | 0.172 [0.135, 0.209] | 0.237 [0.187, 0.283] |
| crnn-beam-unconstrained | `crnn-5348143705d4-T0.888664` | 0.603 [0.543, 0.653] | 0.697 [0.640, 0.747] | 0.827 [0.777, 0.875] | 0.705 [0.646, 0.759] | 0.165 [0.136, 0.197] | 0.151 [0.118, 0.188] | n/a |

Set coverage is the share of truths inside the conformal set at the level fixed on the synthetic conformal split; it holds its level only when the evaluated images are exchangeable with that split, so a drop on the pseudo-real set is the expected warning sign of a distribution shift, not a bug.
<!-- END RENDER pseudo-real-baseline -->

## Limitations

- Trained and measured on synthetic plates only. The pseudo-real set is still synthetic;
  it only shows how quickly accuracy falls under harder conditions.
- The conformal guarantee assumes the calibration and test images are exchangeable. Real
  photos are not exchangeable with synthetic ones, so the stated coverage does not carry
  over to real data until the thresholds are refitted on real labelled crops.
- The fonts are open-licensed approximations of plate lettering; in the Kufi face the
  letter `و` resembles the digit `9`, which only the grammar (a letter must sit between the
  separators) resolves.
- Only the six letters and the two formats of the grammar exist for the model; any other
  plate is read as the closest valid one, and the prediction set is the signal that
  something is off.

## Ethical considerations

Licence plates identify people. The model runs offline, the service stores crops only for
the review queue, and the browser mode (milestone M6) can read a plate without uploading
the photo.

## Reproduce

```bash
uv run plate train crnn            # synthetic pretraining, ONNX export, calibration
uv run plate eval --set synthetic -r easyocr -r crnn-greedy -r crnn-beam
uv run plate eval --set pseudo_real -r easyocr -r crnn-greedy -r crnn-beam
uv run plate docs render
```
