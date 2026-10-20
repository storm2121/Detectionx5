# Insert your own data

Status: v3 (the real-data benchmark pass; v2 was M7, v1 M0). Every command below exists and
runs on synthetic stand-ins; a private set of held-out street photos now runs through the
evaluation part of it (section 4).

The platform runs end to end on synthetic plates. Real photos and labels are optional and
go into `data/`, which the repository keeps as an empty, documented layout. Nothing under
`data/` except `README.md`, `detector.yaml` and the `.gitkeep` files is ever committed: git
ignores the rest, and a pre-commit hook refuses images, videos, archives and CSVs with more
than 50 rows staged there. Real photos stay on your machine.

## 1. Put the files in place

```
data/
├── detector.yaml                      # already present: one class, LP
├── detector/
│   ├── images/train/  images/val/     # full photos (.jpg .jpeg .png .bmp .webp)
│   └── labels/train/  labels/val/     # one .txt per photo, same stem
├── ocr/
│   ├── train/labels.csv               # crop_path,plate_text,format
│   └── val/labels.csv
└── eval/
    ├── labels.csv                     # image_path,plate_text,format,x1,y1,x2,y2[,group]
    └── card.json                      # optional: counts and words that describe the set
```

Recreate the empty skeleton at any time with `uv run plate data init`.

### Detector boxes (`data/detector/`)

One YOLO line per plate: `0 cx cy w h`, all four values normalised to the photo's width
and height. Class `0` is the only class (`LP`). A photo without a label file is treated as
background. Use the same stem for a photo and its label (`IMG_0042.jpg` and
`IMG_0042.txt`).

### Recogniser crops (`data/ocr/`)

`labels.csv` lists plate crops, with `crop_path` relative to the CSV's folder:

```
crop_path,plate_text,format
crops/0001.png,24830-ب-1,standard
crops/0002.png,72173 WW,temporary
```

`plate_text` uses the display spelling: digits, hyphen, one of the six letters `أ ب د ه و
ط`, hyphen, region for standard plates; digits, a space and `WW` for temporary plates.
The review queue exports corrected reads in exactly this layout: reads whose conformal
set holds more than one plate (or whose calibrated confidence is under
`PLATE_REVIEW_THRESHOLD`) wait at `GET /review/queue`; `POST /review/{id}` records the
corrected plate; `POST /review/export` copies every reviewed read's crops into
`PLATE_EXPORT_DIR` (default `data/ocr/train`, in Compose a volume) and appends the rows to its
`labels.csv`. Validate, then fine-tune: `uv run plate data validate`, `uv run plate train crnn`.

### Evaluation photos (`data/eval/`)

`labels.csv` lists whole photos with their true plate and, optionally, the plate box in
pixels:

```
image_path,plate_text,format,x1,y1,x2,y2
photos/car_017_front.jpg,24830-ب-1,standard,412,388,603,431
photos/car_017_rear.jpg,24830-ب-1,standard,,,,
```

Leave all four box columns empty when the box is unknown; detector metrics then skip that
photo while recogniser metrics still use it. A photo with several plates has one row per
plate.

An optional eighth column, `group`, names the photos that are not independent of each other:
several photos of one vehicle, or copies of one photo. Rows that share a group are
resampled together by the bootstrap, so the intervals reflect how many vehicles there are,
not how many photos (ADR 0013). Without the column every row stands alone.

An optional `card.json` beside the CSV holds counts and words that describe the set (how many
photos, what they are, how the text was transcribed, what was left out and why); the harness
copies it into the results, and the README and the console render the set's description from
it, so nothing about the set is typed by hand. It must never hold a plate string.

`uv run plate eval --set data` reads every row from its labelled box, cut exactly where the
service would cut a detection of it, and writes `results/eval_data.json`; `--detect` ignores
the boxes and reads each photo end to end with the shipped ONNX detector, as the service
reads it (the most confident detection; a photo without one counts as a read that returned
nothing), and writes `results/eval_data_e2e.json` with how many photos had no detection.

## 2. Validate

```bash
uv run plate data validate          # exit status 1 on any error
uv run plate data validate --strict # warnings (background photos, non-canonical spellings) fail too
```

The validator decodes every image, checks every YOLO line, and requires every
`plate_text` to be accepted by the plate grammar with a `format` that matches it. Fix every
error before training or evaluating: one bad label silently corrupts every metric computed
from the set.

## 3. What changes once real data exists

| Step | With synthetic data only (today) | Once real data is in place |
|---|---|---|
| Evaluation | `plate eval --set synthetic` and `--set pseudo_real`, labelled synthetic | `plate eval --set data` reads `data/eval/labels.csv` and writes `results/eval_data.json`; `--detect` reads the photos end to end into `results/eval_data_e2e.json` |
| README | "OCR accuracy is not benchmarked on real data" stays | the statement is replaced by the rendered real-data table once `results/eval_data.json` exists |
| Recogniser | CRNN trained on synthetic crops | fine-tuned on `data/ocr/train`, validated on `data/ocr/val` |
| Calibration | temperature fitted on a synthetic split | refitted on a real calibration split, never on the reporting set |
| Conformal sets | thresholds for one view and per number of fused views, fitted on synthetic splits | refitted on real calibration crops and real multi-photo sets (`plate train calibrate`, `plate train calibrate-fused`) |
| Detector | the shipped `models/best.pt`, measured on its own validation split and on synthetic street scenes, where its precision is below its recall (noted, not acted on: it is not fine-tuned on synthetic scenes) | measured on labelled photos with `plate eval-detector --data <detector.yaml>` (written to `results/eval_detector_data.json`), which says whether the synthetic precision gap matters on photographs, and retrained if needed with `plate train detector --data data/detector.yaml` |
| Augmentation sweep | scored on a pseudo-real tuning split | scored on a real validation split; the pseudo-real set becomes a robustness check |
| Console | Evaluation and Models pages show synthetic and pseudo-real results | the real results appear beside them (the Models page's sim-to-real gap gets its real column) |

Every number in the README keeps its set label (synthetic, pseudo-real or data), its n,
its bootstrap interval and its model version, so real and synthetic results can never be
confused.

## 4. What changed now that a real set exists

A private set of street photos of vehicles, held out from every training set as files, is in
`data/eval` with its boxes and hand-checked, twice-transcribed plate text; the data card
describes it and the README's Real photos section renders its results. What that changed,
and what it did not:

- **Evaluation** is real: every recogniser from the labelled boxes (`results/eval_data.json`)
  and end to end with the shipped detector (`results/eval_data_e2e.json`), with intervals
  that resample vehicle groups, and the detector on the same photos
  (`results/eval_detector_data.json`) beside its synthetic scenes. The README's statement
  that OCR accuracy is not benchmarked on real data is replaced by the rendered results.
- **The detector's figures on it are not independent**: every camera photo behind the set
  also has copies in the split the detector was trained on. An independent detector figure
  needs photos it has never seen in any form, labelled the same way under `data/detector`.
- **Calibration is still synthetic.** The temperature and every conformal threshold were
  fitted on synthetic splits, and they stay that way until a real calibration split is
  labelled. The new set is the reporting set: refitting the calibration on it, or
  fine-tuning on it, would make every number it reports meaningless. On it, the calibrated
  confidence is far off and the conformal sets miss the true plate, as the README shows.
- **Nothing was trained on it**: the CRNN is still trained on synthetic crops only, and the
  detector is the shipped one.

## Collect calibration photos before any fine-tuning

The recogniser's temperature and conformal thresholds were fitted on synthetic plates, and the
real-photos block in the README shows that neither carried over to real photos: the calibrated
confidence was far off and the prediction sets missed the true plate. So before fine-tuning on
real crops, collect and label real photos first and split them into three disjoint sets:
fine-tuning, calibration (for the temperature and the conformal thresholds) and test (reported
once, with its interval). Fine-tuning on the only real photos you have, then calibrating and
testing on the same photos, would make every number meaningless.
