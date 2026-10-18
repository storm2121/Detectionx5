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

- **Two recognisers, not one.** On the bundled sample, EasyOCR's English model
  read the digits with far higher confidence than its Arabic model did on the
  same pixels, while the Arabic model is needed for the single letter. Each
  model is pointed only at the field it is good at.
- **The letter field needs cropping to its ink; the digit fields must not be.**
  `ب` is a short glyph adrift in a full-height strip, so scaling that strip
  leaves the letter too small to recognise — on the sample, cropping to the ink
  first turned a low-confidence `د` into a high-confidence `ب`. Applying the
  same crop to the digit fields made them *worse*, so it is deliberately applied
  to the letter alone. (These were single-sample observations from development,
  not benchmarks.)

## Install

Python 3.12, managed by [uv](https://docs.astral.sh/uv/). Dependencies are
declared in `pyproject.toml` and locked in `uv.lock`; on Windows the lock pulls
a CUDA 12.6 build of PyTorch, on Linux a CPU build.

```bash
git clone https://github.com/storm2121/Detectionx5.git
cd Detectionx5

uv sync                          # creates .venv with Python 3.12 and every group
uv run plate --help              # the platform command line
```

Without uv, `requirements.txt` and `requirements-dev.txt` are generated from the
lock for pip users:

```bash
python -m venv .venv             # Python 3.12
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

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
print(result.text)  # '24830-ب-1'
print(result.plate.digits)  # '24830'
print(result.plate.letter)  # 'ب'
print(result.plate.region)  # '1'
print(result.agreement)  # images that independently agreed
```

## HTTP API

Install `requirements.txt`, then start the FastAPI server from the project root:

```bash
uvicorn api:app --host 127.0.0.1 --port 8000
```

The detector and all three EasyOCR readers load once at startup and are reused
across requests. Startup waits for them to be ready and fails if they cannot
load. The first startup may download the OCR weights. Each server worker loads
its own models; use one worker to keep a single copy in memory. The API uses
the same `PLATE_MODEL`, `PLATE_CONF`, and `PLATE_GPU` settings as the CLI.

`GET /health` returns `200` with `{"status":"ok"}` once startup completes.
Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

`POST /read` accepts multipart uploads under the repeated `files` field. Send
one to ten photos **of the same car** (JPEG, PNG, WebP, or BMP; up to 10 MiB
each). For example, in a POSIX shell:

```bash
curl -X POST http://127.0.0.1:8000/read \
  -F "files=@front.jpg" \
  -F "files=@rear.jpg"
```

In Windows PowerShell:

```powershell
curl.exe -X POST http://127.0.0.1:8000/read -F "files=@front.jpg" -F "files=@rear.jpg"
```

Example response:

```json
{
  "plate": "24830-ب-1",
  "fields": {"digits": "24830", "letter": "ب", "region": "1"},
  "confidence": 0.8,
  "images_agreeing": 2,
  "images_processed": 2
}
```

`confidence` is the winning plate's fraction of all OCR- and detector-weighted
votes, between 0 and 1. It measures relative vote support, not a calibrated
probability of correctness. `images_agreeing` counts photos whose best reading
matches the winning plate; each photo counts at most once. Temporary `WW`
plates have `null` letter and region fields. If no valid plate can be read,
the response is still `200`, with `plate` and `fields` set to `null`, confidence
`0`, and `images_agreeing` `0`.

Missing uploads return `422`; empty or corrupt images return `400`; unsupported
image formats return `415`; exceeding the count or size limit returns `413`.
Uploads use temporary files that are removed after each request, including
failed requests. Model inference is serialized within a worker, while health
checks can run independently.

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

The numbers in this section are rendered by `uv run plate docs render` from
[`docs/training_results.csv`](docs/training_results.csv); `uv run plate docs check`
fails if anyone edits them by hand.

<!-- BEGIN RENDER detector-metrics -->
`models/best.pt` (version `648b737411ad`): YOLOv10n fine-tuned for 100 epochs on a single `LP` class, trained on a plate dataset plus photos from the firm's experts. The shipped checkpoint is epoch 90, the epoch Ultralytics selected by its fitness score (0.1 x mAP@50 + 0.9 x mAP@50-95). Values are from that epoch's row of the training log.

| Metric | Value |
|---|---|
| Precision | 0.956 |
| Recall | 0.945 |
| mAP@50 | 0.983 |
| mAP@50-95 | 0.744 |

Set: the detector's own validation split (data). The training log does not record the split size, and a single validation pass gives no confidence interval, so neither n nor a CI is reported for these four numbers.
<!-- END RENDER detector-metrics -->

Full per-epoch metrics are in [`docs/training_results.csv`](docs/training_results.csv).

To use your own weights without editing anything:

```bash
PLATE_MODEL=/path/to/weights.pt python cli.py photo.jpg
```

## Synthetic baseline

The platform measures itself on deterministic synthetic plates until real labelled
data exists. These numbers are rendered from `results/eval_synthetic.json`.

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

## Recogniser: CRNN with grammar-constrained decoding

Beside the EasyOCR path, the platform trains a compact CRNN (CNN, bidirectional LSTM,
CTC) on synthetic crops, decodes it with a beam search pruned by the plate grammar, fits a
temperature so its confidence is calibrated, and wraps each read in a conformal
prediction set. It runs through ONNX Runtime, without PyTorch. Details and limitations are
in [`docs/model_card.md`](docs/model_card.md).

<!-- BEGIN RENDER crnn-training -->
`models/crnn.onnx` (version `5348143705d4`, 5.8 MB, 1440051 parameters): trained on synthetic crops only, 24 epochs of 20000 freshly generated crops each on `cuda`, in 1139.4 s. The kept epoch is 18, chosen by greedy exact match on the synthetic validation split (0.995). Fine-tuned on real data: no. Synthetic results are not real-world accuracy.
<!-- END RENDER crnn-training -->

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

### Multi-view fusion

Several photos of one car are combined in probability space: each view's grammar-valid
hypotheses are renormalised over the union of candidates and multiplied, which is Bayes'
rule for independent views, and every character gets a posterior from aligning the
hypotheses to the winner. The original vote stays selectable (`--fusion vote`). Equations
and properties are in [`docs/methods/fusion.md`](docs/methods/fusion.md); rendered from
`results/eval_views.json`:

<!-- BEGIN RENDER fusion-comparison -->
**Synthetic results are not real-world accuracy.** Multi-view synthetic sets: n = 200 plates with up to 5 views each (generator seed 1007); the first k views of every set are fused; values with bootstrap intervals over sets.

Multi-view sets (exact match of the fused read; n = 200 sets, bootstrap over sets):

| Recogniser | Fusion | 1 view(s) | 3 view(s) | 5 view(s) |
|---|---|---|---|---|
| easyocr | legacy_vote | 0.295 [0.235, 0.360] | 0.545 [0.475, 0.615] | 0.585 [0.515, 0.650] |
| easyocr | probabilistic | 0.295 [0.235, 0.360] | 0.465 [0.395, 0.530] | 0.520 [0.445, 0.590] |
| easyocr | probabilistic_weighted | 0.295 [0.235, 0.360] | 0.475 [0.405, 0.540] | 0.520 [0.445, 0.585] |
| crnn-greedy | legacy_vote | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-greedy | probabilistic | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-greedy | probabilistic_weighted | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | legacy_vote | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | probabilistic | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | probabilistic_weighted | 0.990 [0.975, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |

Calibration and conformal sets of the fused read (fused sets apply the single-view threshold, so beyond one view their coverage is measured, not guaranteed):

| Recogniser | Fusion | Views | ECE | Set coverage | Mean set size |
|---|---|---|---|---|---|
| easyocr | legacy_vote | 1 | 0.166 [0.120, 0.217] | n/a | n/a |
| easyocr | legacy_vote | 5 | 0.102 [0.072, 0.153] | n/a | n/a |
| easyocr | probabilistic | 1 | 0.166 [0.120, 0.217] | n/a | n/a |
| easyocr | probabilistic | 5 | 0.187 [0.139, 0.242] | n/a | n/a |
| easyocr | probabilistic_weighted | 1 | 0.160 [0.116, 0.211] | n/a | n/a |
| easyocr | probabilistic_weighted | 5 | 0.202 [0.153, 0.259] | n/a | n/a |
| crnn-greedy | legacy_vote | 1 | 0.010 [0.000, 0.025] | n/a | n/a |
| crnn-greedy | legacy_vote | 5 | 0.003 [0.001, 0.006] | n/a | n/a |
| crnn-greedy | probabilistic | 1 | 0.010 [0.000, 0.025] | n/a | n/a |
| crnn-greedy | probabilistic | 5 | 0.000 [0.000, 0.000] | n/a | n/a |
| crnn-greedy | probabilistic_weighted | 1 | 0.010 [0.000, 0.025] | n/a | n/a |
| crnn-greedy | probabilistic_weighted | 5 | 0.000 [0.000, 0.000] | n/a | n/a |
| crnn-beam | legacy_vote | 1 | 0.010 [0.000, 0.025] | n/a | n/a |
| crnn-beam | legacy_vote | 5 | 0.004 [0.001, 0.007] | n/a | n/a |
| crnn-beam | probabilistic | 1 | 0.010 [0.003, 0.018] | 0.900 [0.855, 0.940] | 0.900 [0.855, 0.940] |
| crnn-beam | probabilistic | 5 | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| crnn-beam | probabilistic_weighted | 1 | 0.033 [0.024, 0.051] | 0.280 [0.220, 0.345] | 0.280 [0.220, 0.345] |
| crnn-beam | probabilistic_weighted | 5 | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
<!-- END RENDER fusion-comparison -->

### Pseudo-real stand-in

A heavier augmentation preset stands in for the gap between synthetic and real photos
until real labelled data exists. Rendered from `results/eval_pseudo_real.json`.

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

## Configuration

Every setting in [`plate_reader/settings.py`](plate_reader/settings.py) (re-exported
by `config.py`) has a sensible default and can be overridden by environment variable:

| Variable | Default | Purpose |
|---|---|---|
| `PLATE_MODEL` | `models/best.pt` | detector weights |
| `PLATE_OUTPUT_DIR` | `output/` | where `--save-crops` writes |
| `PLATE_CONF` | `0.25` | detection confidence threshold |
| `PLATE_GPU` | `0` | set to `1` to run EasyOCR on the GPU |
| `PLATE_DATA_DIR` | `data/` | the real-data placeholder (see `data/README.md`) |
| `PLATE_RESULTS_DIR` | `results/` | where evaluation and training write metrics JSON |

## Layout

```
config.py               paths and thresholds, all overridable
cli.py                  command-line entry point
gui.py                  ttkbootstrap desktop app
api.py                  FastAPI upload and health endpoints
plate_reader/
    detector.py         YOLO wrapper, IoU de-duplication, padded crops
    segment.py          plate isolation, separator detection, field cutting
    preprocess.py       thresholding variants for the OCR ensemble
    ocr.py              EasyOCR backends behind a swappable interface
    grammar.py          the plate formats as one finite automaton
    normalize.py        text repair and lenient parsing onto the grammar
    settings.py         typed PLATE_* configuration
    docs_render.py      renders README numbers from results; detects drift
    data/               the real-data layout and its validator
    synthetic/          deterministic synthetic plates (fonts, render, augment)
    eval/               evaluation harness, bootstrap intervals, reports
    crnn/               CRNN model, CTC decoders, calibration, conformal, ONNX runtime
    training/           CRNN training, ONNX export, calibration, detector training
    fusion.py           combining several photos (legacy vote baseline)
    cli/                the `plate` command line
    pipeline.py         orchestration and voting
models/best.pt          fine-tuned detector
models/crnn.onnx        CRNN recogniser (with crnn.json metadata and crnn.pt weights)
results/                metrics JSON the docs render from
data/                   placeholder for real data (README, layout, detector.yaml)
docs/                   ADRs, training log, insert-your-own-data guide
tools/repo_guards.py    pre-commit and CI guards
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

The API tests use FastAPI's `TestClient` with fake detector/OCR models and the
real multi-photo voting pipeline, so they need no model downloads. They cover
startup and model reuse, agreement and confidence, temporary and unreadable
plates, upload validation, and temporary-file cleanup. Run them on their own
with `pytest tests/test_api.py -q`.

To include the real-model API regression test, which reads `samples/car.jpg`
and checks for `24830-ب-1`, enable it explicitly. The OCR weights must be
cached or downloadable on the first run:

```bash
PLATE_TEST_MODELS=1 pytest tests -q
```

In Windows PowerShell:

```powershell
$env:PLATE_TEST_MODELS = "1"
.\.venv\Scripts\python.exe -m pytest tests -q
```

This checks single and multi-file requests using repeated copies of the sample;
distinct photos of the same car are still needed to assess real-world agreement.

## Limitations

Worth being straight about:

- <!-- BEGIN RENDER ocr-benchmark-status -->
**OCR accuracy is not benchmarked on real data.** No labelled real evaluation set exists yet, so no real-world accuracy figure is claimed. `docs/insert_your_own_data.md` explains where real photos and labels go.
<!-- END RENDER ocr-benchmark-status -->
  The pipeline is verified end-to-end on the bundled sample and the segmentation
  logic is covered by tests. The detector's metrics above come from its own
  validation split. Every synthetic number in this README is labelled as
  synthetic: synthetic results are not real-world accuracy.
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
- Detector training data: a plate dataset plus photos from the firm's experts
- OCR: [EasyOCR](https://github.com/JaidedAI/EasyOCR), Apache-2.0
- Synthetic-plate fonts: SIL Open Font License 1.1 (see `plate_reader/synthetic/fonts/`)

Licensed under **AGPL-3.0** — see [LICENSE](LICENSE). This is required rather
than chosen: the fine-tuned weights derive from YOLOv10/Ultralytics, which are
AGPL-3.0, so anything distributed from them inherits that licence.
