# Insert your own data

Status: v2 (M7; v1 was M0). Every command below exists and runs on synthetic stand-ins today.

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
    └── labels.csv                     # image_path,plate_text,format,x1,y1,x2,y2
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
photo while recogniser metrics still use it.

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
| Evaluation | `plate eval --set synthetic` and `--set pseudo_real`, labelled synthetic | `plate eval --set data` reads `data/eval/labels.csv` and writes `results/eval_data.json` |
| README | "OCR accuracy is not benchmarked on real data" stays | the statement is replaced by the rendered real-data table once `results/eval_data.json` exists |
| Recogniser | CRNN trained on synthetic crops | fine-tuned on `data/ocr/train`, validated on `data/ocr/val` |
| Calibration | temperature fitted on a synthetic split | refitted on `data/ocr/val` |
| Conformal sets | thresholds for one view and per number of fused views, fitted on synthetic splits | refitted on real calibration crops and real multi-photo sets (`plate train calibrate`, `plate train calibrate-fused`) |
| Detector | the shipped `models/best.pt`, measured on its own validation split and on synthetic street scenes, where its precision is below its recall (noted, not acted on: it is not fine-tuned on synthetic scenes) | measured on `data/detector` with `plate eval-detector --data data/detector.yaml` (written to `results/eval_detector_data.json`), which says whether the synthetic precision gap matters on photographs, and retrained if needed with `plate train detector --data data/detector.yaml` |
| Augmentation sweep | scored on a pseudo-real tuning split | scored on a real validation split; the pseudo-real set becomes a robustness check |
| Console | Evaluation and Models pages show synthetic and pseudo-real results | the real results appear beside them (the Models page's sim-to-real gap gets its real column) |

Every number in the README keeps its set label (synthetic, pseudo-real or data), its n,
its bootstrap interval and its model version, so real and synthetic results can never be
confused.
