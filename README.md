# Moroccan Licence-Plate Reader

Detects and reads Moroccan vehicle licence plates from photographs. Detection
uses a YOLOv10 model fine-tuned on Moroccan plates; reading is done with
EasyOCR. **Everything runs locally — no API key, no network calls at inference
time, no per-image cost.**

```console
$ python cli.py samples/car.jpg
Detecting plates in car.jpg...
  plate 1: 24830-ب-1 [fields, detector 0.43]

Plate: 24830-ب-1
```

---

## The problem this project actually solves

A Moroccan civilian plate is laid out as three printed fields divided by two
vertical bars:

```
┌──────────────────────────┐
│   24830  │  ب  │  1      │
└──────────────────────────┘
   number    letter  region
```

Pointing a general-purpose OCR engine at that crop goes badly, and the reason
is specific: **the printed separator bars are themselves read as characters.**
EasyOCR sees them as an Arabic alif (`ا`) or as the digit `1`, which corrupts
every field at once. On the bundled sample, reading the plate as one line
produces `74!30`, `2/930`, `ا ' ب ر` and similar noise — nothing parseable.

The bars are, however, trivial to find geometrically: they are the only marks
that are tall and extremely narrow. Locating them and cutting the plate into
its three fields means each field can be read on its own, with an alphabet
restricted to what that field can legally contain. That one change is the
difference between unusable output and a correct read.

Two further details mattered more than expected:

- **Two recognisers, not one.** EasyOCR's English model reads the digits far
  more accurately than its Arabic model does (0.99 vs 0.45 confidence on the
  same pixels), while the Arabic model is needed for the single letter. Each
  model is pointed only at the field it is good at.
- **The letter field needs cropping to its ink; the digit fields must not be.**
  `ب` is a short glyph adrift in a full-height strip, so scaling that strip
  leaves the letter too small to recognise — cropping to the ink first took it
  from `د` at 0.26 confidence to `ب` at 0.97. Applying the same crop to the
  digit fields made them *worse*, so it is deliberately applied to the letter
  alone.

## Install

Python 3.10 or newer.

```bash
git clone https://github.com/storm2121/Detectionx5.git
cd Detectionx5

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

A virtual environment is strongly recommended. `requirements.txt` pins
`numpy<2` because much of the ultralytics/pandas stack in circulation is still
built against the numpy 1.x C ABI; installing into an environment that already
has numpy 2.x produces `numpy.dtype size changed, may indicate binary
incompatibility` at import.

EasyOCR downloads its recognition models (~100 MB) the first time it runs.
That is the only network access the project makes, and it happens once.

## Usage

**Command line**

```bash
python cli.py samples/car.jpg                 # read one image
python cli.py front.jpg side.jpg rear.jpg     # vote across several photos
python cli.py samples/car.jpg --json          # machine-readable output
python cli.py samples/car.jpg --save-crops    # also write the cropped plates
python cli.py samples/car.jpg --conf 0.4      # stricter detection threshold
```

Exit status is `0` when a plate was read and `1` when none could be, so the
tool composes with shell scripting.

**Desktop app**

```bash
python gui.py
```

Pick one or more images and press *Read plates*. Detection and OCR run on a
worker thread, so the window stays responsive.

**As a library**

```python
from plate_reader import read_images

result = read_images(["samples/car.jpg"])
print(result.text)              # '24830-ب-1'
print(result.plate.digits)      # '24830'
print(result.plate.letter)      # 'ب'
print(result.plate.region)      # '1'
print(result.agreement)         # images that independently agreed
```

## How it works

```
photo
  │
  ├─ 1. detect      YOLOv10 finds plate boxes, near-duplicates merged by IoU
  ├─ 2. isolate     crop trimmed to the bright plate body
  ├─ 3. segment     separator bars located by aspect ratio, plate cut in three
  ├─ 4. read        digits via the English model, letter via the Arabic model,
  │                 each field over several thresholdings
  ├─ 5. vote        weighted by OCR and detector confidence
  └─ 6. validate    parsed against the legal plate grammar
```

If the separator bars cannot be found — a damaged plate, an odd angle, or the
temporary `WW` format — the plate is read as a single line instead. That path
is less accurate but still frequently correct.

Recognised formats:

| Format | Example | Notes |
|---|---|---|
| Standard | `24830-ب-1` | digits, one of `أ ب د ه و ط`, region code |
| Temporary | `72173 WW` | digits followed by the `WW` marker |

Text repair is handled in [`plate_reader/normalize.py`](plate_reader/normalize.py):
Arabic-Indic digits are converted, every Unicode spelling of the six letters is
folded onto one canonical form, and letter/digit lookalikes (`O`→`0`, `I`→`1`)
are undone inside groups that are meant to be numeric.

## Detection model

`models/best.pt` — YOLOv10n fine-tuned for 100 epochs on a single `LP` class.

| Metric | Value |
|---|---|
| Precision | 0.958 |
| Recall | 0.957 |
| mAP@50 | 0.987 |
| mAP@50-95 | 0.743 |

Full per-epoch metrics are in [`docs/training_results.csv`](docs/training_results.csv).

To use your own weights without editing anything:

```bash
PLATE_MODEL=/path/to/weights.pt python cli.py photo.jpg
```

## Configuration

Every setting in [`config.py`](config.py) has a sensible default and can be
overridden by environment variable:

| Variable | Default | Purpose |
|---|---|---|
| `PLATE_MODEL` | `models/best.pt` | detector weights |
| `PLATE_OUTPUT_DIR` | `output/` | where `--save-crops` writes |
| `PLATE_CONF` | `0.25` | detection confidence threshold |
| `PLATE_GPU` | `0` | set to `1` to run EasyOCR on the GPU |

## Layout

```
config.py               paths and thresholds, all overridable
cli.py                  command-line entry point
gui.py                  ttkbootstrap desktop app
plate_reader/
    detector.py         YOLO wrapper, IoU de-duplication, padded crops
    segment.py          plate isolation, separator detection, field cutting
    preprocess.py       thresholding variants for the OCR ensemble
    ocr.py              EasyOCR backends behind a swappable interface
    normalize.py        text repair, plate grammar, validation
    pipeline.py         orchestration and voting
models/best.pt          fine-tuned detector
samples/car.jpg         sample image
tests/                  pytest suite
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests -q
```

The text tests need nothing beyond pytest. The segmentation tests use the
bundled sample and the committed weights, and skip automatically if those are
unavailable.

## Limitations

Worth being straight about:

- **OCR accuracy is not benchmarked.** The pipeline is verified end-to-end on
  the bundled sample and the segmentation logic is covered by tests, but there
  is no labelled evaluation set, so no accuracy figure is claimed. The
  detector's metrics above come from its own validation split.
- **The `WW` temporary format has no separator bars**, so it takes the
  whole-plate fallback path and is read less reliably.
- Plates that are heavily skewed, motion-blurred, or badly lit will fail
  segmentation and fall back to the weaker path. No perspective correction is
  applied.
- Only the six letters `أ ب د ه و ط` are accepted; other series are rejected
  by design rather than guessed at.
- CPU inference takes roughly a second or two per image. Set `PLATE_GPU=1` if
  you have CUDA available.

## Credits and licence

- Detection architecture: [YOLOv10](https://github.com/THU-MIG/yolov10) (THU-MIG), AGPL-3.0
- Training dataset: [Moroccan License Plate Detection](https://universe.roboflow.com/storm-i5hxc/moroccan-license-plate-detection-pyfe7) via Roboflow, CC BY 4.0
- OCR: [EasyOCR](https://github.com/JaidedAI/EasyOCR), Apache-2.0

Licensed under **AGPL-3.0** — see [LICENSE](LICENSE). This is required rather
than chosen: the fine-tuned weights derive from YOLOv10/Ultralytics, which are
AGPL-3.0, so anything distributed from them inherits that licence.
