# Data card

Status: v3 (the real-data benchmark pass; v2 was M6 and M7, v1 the follow-up to M4).
Synthetic results are not real-world accuracy. Every count on this page is rendered from
`results/*.json` by `uv run plate docs render`.

## What data the platform uses today

- **Held-out street photos** under `data/eval` (gitignored and never committed): street
  photos of vehicles, held out from every training set as files, with boxes and
  hand-transcribed plate text. They are the reporting set, used for evaluation only:
  nothing is trained, calibrated or tuned on them. Their metrics, and only their metrics,
  are in `results/eval_data.json` (read from the labelled boxes),
  `results/eval_data_e2e.json` (end to end with the detector) and
  `results/eval_detector_data.json` (the detector). [The real benchmark](#the-real-benchmark)
  below says what they are and what they are not.
- **Synthetic plates** from `plate_reader/synthetic/`: standard and temporary plates
  rendered from the plate grammar with open-licensed fonts, composed onto procedural
  bodywork or street scenes and degraded by documented, strength-scaled augmentations
  (`plate_reader/synthetic/augment.py` lists every distribution). Every split has its own
  fixed seed (`plate_reader/synthetic/splits.py`), so training, validation, calibration,
  conformal, test, pseudo-real and multi-view sets never share a sample, and a seed
  reproduces every byte.
- **The pseudo-real set**: the same generator with a heavier augmentation preset. It is a
  stand-in for the gap between synthetic and real photos, labelled pseudo-real everywhere,
  and it is still synthetic. A separate pseudo-real tuning split (its own seed) scores the
  augmentation sweep, so the evaluation set never steers a choice it later measures.
- **Street scenes**: procedural scenes with one plate on a car, and multi-view sets of the
  same car in several scenes (`make_scene_views`), which are the parity fixtures of the
  browser runtime and the console's sample photos.
- **The detector's training data**: the shipped detector was trained on a publicly
  available plate dataset released under CC BY 4.0, plus photographs from the firm's
  experts; that data is not in this repository.
- **Real training data**: none. Nothing real is in the repository; `data/` is a documented
  placeholder (`data/README.md`, `docs/insert_your_own_data.md`) checked by
  `plate data validate`, and the private photos live only in a working copy.

## The real benchmark

<!-- BEGIN RENDER real-set -->
Set: data (`data/eval/labels.csv`, private and not in the repository): street photos of vehicles, held out from every training set as files, with every box checked by eye and every plate transcribed twice and checked against the plate grammar, n = 258 photos holding 261 labelled plates. Every photo is an augmented copy of one of 196 camera photos (32 contrast changed, 51 noise added, 43 shifted, 41 rotated, 47 mirrored and 44 upside down); the mirrored and upside-down copies were flipped back exactly, so every plate reads the right way round. Every camera photo behind this split also has copies in the split the detector was trained on: the detector has seen these scenes, so the end-to-end and detector figures below are not independent of its training data; the recogniser has only ever seen synthetic plates.

The plate text was transcribed by eye, crop by crop: every plate crop was read twice on differently ordered contact sheets, every string was checked against the plate grammar, and every disagreement, invalid or doubtful reading was read a third time at a higher zoom. The two passes agreed on 255 of 260 crops, and on all 224 where both gave a reading the grammar accepts; the third pass accepted 26 of the 67 crops it saw. 219 plates in 218 photos are labelled (133 distinct vehicles); 42 were left out: 27 illegible in the photo, 12 outside the grammar and 3 with no plate in the box. The benchmark therefore measures plates a person can read, and does not count the ones left out as failures.

Values with 95% bootstrap intervals that resample the 132 vehicle groups (a vehicle with every photo it appears in) instead of single photos, since copies of one photo and repeat photos of one vehicle are not independent (1000 resamples).

Read end to end, the set is 218 photos (every photo with at least one labelled plate), the labelled boxes ignored.

The detector is measured on 257 photos holding 260 boxes: every valid box of the held-out street photos, the plates whose text was left out included, and the photo whose only box is degenerate left out.
<!-- END RENDER real-set -->

How it was built:

- **Photos.** The split's photos were copied under neutral names into `data/eval/images`;
  a private mapping file beside them links each to its source file. The mirrored and
  upside-down copies were flipped back exactly, with their boxes, so every plate reads the
  right way round; no camera produces a mirrored plate. The rotated and shifted copies stay
  as they are: no exact inverse exists, and each still shows a real plate. The previous set
  of web photos is retired from the benchmark.
- **Boxes.** Each normalised YOLO box became integer pixel coordinates `x1,y1,x2,y2`, one
  row per plate; every box was seen on a contact sheet during transcription. A box that
  collapsed to a point (its plate lies outside a rotated photo) is excluded.
- **Text.** Every plate was cropped with its box plus the padding the pipeline gives a
  detection, small crops were upscaled, and the crops were laid out on contact sheets with a
  large index above each. Two passes read every sheet into the grammar's display spelling,
  the second over a different order and layout; every string was validated with
  `plate_reader.grammar`. A crop on which the passes agreed, whose reading the grammar
  accepted and which neither pass marked as doubtful was accepted; every other crop
  (disagreement, invalid, unreadable, or dirty, cut off, blurred or glared) went to a third
  pass at a higher zoom with a contrast-equalised copy and a wider view. What the third pass
  could not settle is left out of `labels.csv` and listed, with the box, the three readings
  and the reason, in a private `unresolved.csv` for Mohamed to settle. Both passes were made
  by the same transcriber (the AI agent that built the set), so they are not independent annotators; the
  grammar check and the third pass are what catch a slip.
- **Groups.** The eighth column of `labels.csv`, `group`, joins a vehicle with every photo it
  appears in (the connected components of "same plate" and "same camera photo"); the
  bootstrap resamples these groups (ADR 0013).
- **Detector labels.** The detector is measured on every valid box, including plates whose
  text was left out, written as YOLO labels beside the photos with a private
  `detector.yaml`; the photo whose only box is degenerate is left out of that measurement.
- **What is not done with it.** Neither the temperature nor any conformal threshold is
  refitted on it, and nothing is fine-tuned on it.

## Splits

Every synthetic split has its own seed in `plate_reader/synthetic/splits.py`; samples are
seeded from `(seed, kind, index, view)`, so no two splits share a sample.

| Split | Seed | Used for |
|---|---|---|
| `train` | 1001 | CRNN training crops (generated on the fly) |
| `val` | 1002 | choosing the kept training epoch |
| `calibration` | 1003 | fitting the temperature |
| `conformal` | 1004 | single-view conformal thresholds |
| `test` | 1005 | the synthetic evaluation set, the parity fixtures and the console's samples |
| `pseudo_real` | 1006 | the pseudo-real evaluation set |
| `views` | 1007 | multi-view evaluation sets |
| `views_calibration` | 1008 | conformal thresholds per number of fused views |
| `pseudo_real_tune` | 1009 | scoring the augmentation sweep |

## Assumptions the data encodes

- **Formats**: standard plates are digits (one to five), one of the six letters
  `أ ب د ه و ط`, and a region code (one or two digits); temporary plates are digits followed
  by `WW`. The temporary format accepts **one to six digits**, as the architecture
  specifies, until Mohamed confirms the range with the firm (the original reader accepted
  five or six). The grammar automaton (`plate_reader/grammar.py`) is the single place to
  change it.
- **Appearance**: the bundled fonts approximate plate lettering; backgrounds are procedural,
  not photographs of vehicles; the generator draws no country band, dealer plates or
  damaged plates.

## Known gaps

The conformal thresholds and the temperature come from synthetic splits, and so does
every metric except the real-photo evaluation. They describe the synthetic distribution
only: on the real photos neither the confidence nor the sets hold. The calibration remains
synthetic until a separate real calibration split is labelled
(`docs/insert_your_own_data.md`); the reporting set above must not be used for it.

The real benchmark's own limits: its photos are augmented copies of fewer camera photos,
several of the same vehicle; the detector has seen every one of its scenes in training; and
it leaves out plates nobody can read, so it does not count them as failures.

## Privacy

Licence plates identify people. Real photos and crops stay out of git (`.gitignore` and a
pre-commit check), the service stores crops only for the review queue, and the browser mode
reads plates without uploading the photo.
