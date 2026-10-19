# Model card: CRNN plate recogniser

Status: v2 (milestones M6 and M7; v1 was M2). Every number on this page is rendered by
`uv run plate docs render` from `results/train_crnn.json`, `results/calibration_crnn.json`,
`results/sweep.json` and `results/eval_*.json`; `uv run plate docs check` fails if one is
edited by hand. Synthetic results are not real-world accuracy.

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
- Prediction sets: split conformal prediction at the levels in `models/crnn.json`, with one
  threshold for a single view and one per number of fused views (`conformal_fused`), chosen
  by the number of views that proposed a plate.
- Runtimes: ONNX Runtime in the service and the worker (torch-free), and ONNX Runtime Web in
  the console's in-browser mode, whose TypeScript post-processing reproduces the Python
  pipeline on every committed parity fixture (`results/parity_fixtures.json`).
- Files: `models/crnn.onnx` (opset 17, dynamic batch), `models/crnn.json` (charset
  fingerprint, input contract, temperature, beam width, conformal thresholds),
  `models/crnn.pt` (PyTorch weights, for the parity test and for fine-tuning).
- Version: the first twelve hexadecimal digits of the ONNX file's SHA-256.

<!-- BEGIN RENDER crnn-training -->
`models/crnn.onnx` (version `5348143705d4`, 5.8 MB, 1440051 parameters): trained on synthetic crops only, 24 epochs of 20000 freshly generated crops each on `cuda`, in 1139.4 s. The kept epoch is 18, chosen by greedy exact match on the synthetic validation split (0.995). Fine-tuned on real data: no. Augmentation: the generator's default degradation bounds. Synthetic results are not real-world accuracy.
<!-- END RENDER crnn-training -->

## The detector

The detector (`models/best.pt`, exported as `models/detector.onnx`) is the YOLOv10n model
the platform inherited. The detector was trained on a publicly available plate dataset
released under CC BY 4.0, plus photographs from the firm's experts; the dataset is not named
here at the owner's request and full attribution is available from the author.

Measured independently of its training only on synthetic street scenes it never saw,
with `plate eval-detector` (Ultralytics validation):

<!-- BEGIN RENDER detector-synthetic -->
**Synthetic results are not real-world accuracy.** `models/best.pt` on the `val` split of a synthetic street-scene set: 150 scenes holding 135 plates (15 with no plate), generator seed 1005, version 1, image size 640. One Ultralytics validation pass, so no interval; procedural scenes say nothing about real photos.

| Metric | Value |
|---|---|
| Precision | 0.729 |
| Recall | 0.948 |
| mAP@50 | 0.843 |
| mAP@50-95 | 0.602 |

Precision is below recall by 0.219: on these scenes the detector proposes boxes that are not plates more often than it misses a plate. The gap is noted and not acted on: the detector is not fine-tuned on synthetic scenes, and only a labelled set of real photos can say whether it matters.

Reproduce: `uv run plate synth scenes --n 300 --seed 1005 --val-fraction 0.5 --out synthetic/scenes-eval` then `uv run plate eval-detector --data synthetic/scenes-eval/detector.yaml`.
<!-- END RENDER detector-synthetic -->

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

## Augmentation sweep (domain randomisation)

`plate sweep` asks which strengths of the generator's degradations transfer best to the
pseudo-real set: every trial scales five groups of augmentation bounds, fine-tunes the
shipped CRNN briefly on crops generated with them, and scores exact match on a pseudo-real
tuning split with its own seed (never the pseudo-real evaluation set). Short fine-tunings
rank configurations; a full training with the winner is then compared with the weights in
service, on the same crops and under a rule fixed before it runs (ADR 0010). Rendered from
`results/sweep.json`.

<!-- BEGIN RENDER augmentation-sweep -->
**Synthetic results are not real-world accuracy.** 8 trials, each fine-tuning `crnn.pt` for 3 epochs of 10000 synthetic crops on `cuda`, scored by greedy exact match on 1000 pseudo-real tuning crops (seed 1009) with 95% bootstrap intervals; trial 0 is the default configuration, and differences are paired against it over the same crops. The weights the trials started from score 0.692 [0.663, 0.719] before any fine-tuning. A full training with the best configuration was compared with the shipped weights and did not replace them; the comparison follows.

| Trial | geometry | photometry | blur | noise | clutter | Pseudo-real exact match | Difference to the shipped configuration | Synthetic validation |
|---|---|---|---|---|---|---|---|---|
| 5 (best) | 1.94 | 1.51 | 0.95 | 1.48 | 0.59 | 0.726 [0.698, 0.750] | 0.062 [0.041, 0.085] | 0.985 |
| 6 | 1.21 | 0.61 | 1.85 | 1.03 | 0.89 | 0.718 [0.688, 0.744] | 0.054 [0.033, 0.075] | 0.980 |
| 3 | 1.50 | 1.04 | 1.10 | 1.80 | 0.55 | 0.706 [0.676, 0.732] | 0.042 [0.023, 0.063] | 0.985 |
| 4 | 0.56 | 0.51 | 1.59 | 1.47 | 1.67 | 0.706 [0.678, 0.732] | 0.042 [0.022, 0.065] | 0.980 |
| 1 | 1.07 | 1.35 | 1.15 | 1.06 | 0.90 | 0.698 [0.669, 0.725] | 0.034 [0.014, 0.053] | 0.985 |
| 2 | 1.22 | 0.92 | 1.72 | 1.90 | 0.85 | 0.690 [0.662, 0.718] | 0.026 [0.005, 0.049] | 0.980 |
| 7 | 0.72 | 1.46 | 0.94 | 1.10 | 0.51 | 0.673 [0.645, 0.702] | 0.009 [-0.013, 0.033] | 0.975 |
| 0 (default) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.664 [0.635, 0.692] | reference | 0.985 |
<!-- END RENDER augmentation-sweep -->

### The best configuration, trained in full

`plate train crnn --augment-from results/sweep.json` repeats the shipped recipe from scratch
with the best trial's bounds, calibrates the result like the shipped model, and
`plate compare-crnn` reads both models with the served decoder on the same crops. Rendered
from `results/crnn_comparison.json`:

<!-- BEGIN RENDER crnn-comparison -->
**Synthetic results are not real-world accuracy.** Before: `crnn-5348143705d4-T0.888664`. Retrained: `crnn-3d1b26202da9-T0.800804` (trained from scratch with the shipped recipe, 24 epochs of 20000 crops, and the augmentation of sweep trial 5). Both read through the grammar-constrained beam with their own calibrated temperature, on the same 2000 crops per set; differences are a paired percentile bootstrap (1000 resamples, 95% intervals).

| Set | Before | Retrained | Retrained minus before | Right only before | Right only retrained |
|---|---|---|---|---|---|
| Synthetic test split (decides) | 0.9945 [0.9915, 0.9975] | 0.9975 [0.9950, 0.9995] | 0.0030 [-0.0005, 0.0065] | 3 | 9 |
| Pseudo-real set (reported only) | 0.6675 [0.6465, 0.6885] | 0.7305 [0.7120, 0.7500] | 0.0630 [0.0465, 0.0790] | 64 | 190 |

The rule, fixed before the comparison ran: adopt the new weights only if the paired difference in exact match (new minus old) on the synthetic test split has a bootstrap interval entirely above zero. Outcome: the previous weights stay in service; the retrained ones are not committed, and the shipped CRNN, its calibration and every other result are unchanged.
<!-- END RENDER crnn-comparison -->

## Evaluation

On labelled photos of real cars, read end to end with the shipped detector and cropped
as the service crops them (`results/eval_data.json`; the photos stay private):

<!-- BEGIN RENDER real-photos -->
Set: data (`data/eval/labels.csv`, private and not in the repository), n = 12 labelled photos of real cars, each read end to end: the shipped detector finds the plate and the photo is cropped exactly as the service crops it. Values with 95% bootstrap intervals over photos (1000 resamples). Twelve photos give a wide interval, and the set is small and easy (clean rear shots).

| Recogniser | Version | Exact match | Digits | Letter | Region | Character error rate |
|---|---|---|---|---|---|---|
| EasyOCR path | `easyocr-1.7.2+segmentation` | 8% (0 to 25) | 17% (0 to 42) | 18% (0 to 42) | 18% (0 to 44) | 84% (63 to 100) |
| CRNN, greedy | `crnn-5348143705d4-T0.888664` | 25% (0 to 50) | 33% (8 to 58) | 27% (0 to 55) | 36% (10 to 67) | 24% (12 to 39) |
| CRNN, constrained beam | `crnn-5348143705d4-T0.888664` | 33% (8 to 58) | 50% (25 to 75) | 64% (33 to 91) | 64% (33 to 91) | 25% (10 to 43) |

Letter and region are scored on the 11 standard plates; a temporary plate has neither. A lower character error rate is better.

Calibration does not carry over: the constrained beam's confidence, temperature-scaled on synthetic plates, has an expected calibration error of 47% (25 to 68) on these photos, and its conformal sets, whose thresholds were fitted on synthetic splits, hold the true plate for 0% (0 to 0) of them. Both must be refitted on real calibration photos before a confidence or a set is trusted.

The sim-to-real gap: exact match of the same recognisers on the synthetic test set and on these photos. Synthetic results are not real-world accuracy; the synthetic column is the development harness's, shown only to measure the gap.

| Recogniser | Synthetic test set (n = 300) | Real photos (n = 12) | Gap |
|---|---|---|---|
| EasyOCR path | 35% (30 to 41) | 8% (0 to 25) | 27 points lower on real photos |
| CRNN, greedy | 99% (98 to 100) | 25% (0 to 50) | 74 points lower on real photos |
| CRNN, constrained beam | 99% (98 to 100) | 33% (8 to 58) | 66 points lower on real photos |

Reproduce (with the photos in place): `uv run plate eval --set data -r easyocr -r crnn-greedy -r crnn-beam --views 0 --note "small and easy (clean rear shots)"`.
<!-- END RENDER real-photos -->

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

- Trained and calibrated on synthetic plates only, and measured on real photos only
  through a small private set, whose intervals are wide. The pseudo-real set is still
  synthetic; it only shows how quickly accuracy falls under harder conditions.
- The conformal guarantee assumes the calibration and test images are exchangeable. Real
  photos are not exchangeable with synthetic ones, so the stated coverage does not carry
  over to real data until the thresholds are refitted on real labelled crops.
- The fonts are open-licensed approximations of plate lettering; in the Kufi face the
  letter `و` resembles the digit `9`, which only the grammar (a letter must sit between the
  separators) resolves.
- Temporary (`WW`) plates are assumed to carry one to six digits, as the architecture
  specifies, until the range is confirmed with the firm (see `docs/data_card.md`).
- Only the six letters and the two formats of the grammar exist for the model; any other
  plate is read as the closest valid one, and the prediction set is the signal that
  something is off.

## Ethical considerations

Licence plates identify people. The model runs offline, the service stores crops only for
the review queue, and the console's in-browser mode reads a plate without uploading the
photo. Reads that cannot be certified go to a person instead of being acted on.

## Reproduce

```bash
uv run plate train crnn            # synthetic pretraining, ONNX export, calibration
uv run plate train calibrate-fused # conformal thresholds per number of fused views
uv run plate eval --set synthetic -r easyocr -r crnn-greedy -r crnn-beam
uv run plate eval --set pseudo_real -r easyocr -r crnn-greedy -r crnn-beam
uv run plate eval --set views
uv run plate export fixtures       # parity fixtures for the PyTorch, ONNX and browser runtimes
uv run plate export web            # the automaton and OpenCV reference cases for the browser
uv run plate sweep                 # the augmentation sweep
uv run plate train crnn --augment-from results/sweep.json --models-dir .cache/crnn-sweep/models --results-dir .cache/crnn-sweep/results
uv run plate compare-crnn --old models/crnn.onnx --new .cache/crnn-sweep/models/crnn.onnx --new-summary .cache/crnn-sweep/results/train_crnn.json
uv run plate docs render
```
