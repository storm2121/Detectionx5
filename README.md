# DetectionX5: a Moroccan licence-plate reading platform

DetectionX5 reads Moroccan licence plates from photos. It finds the plate in each photo,
reads it with a recogniser that can only produce strings the plate grammar allows, fuses
several photos of the same car into one read, reports a calibrated confidence and a
conformal prediction set, and sends the reads it cannot certify to a human review queue
whose corrections become training data. A Vue console shows every step, and can run both
models in the browser so that a photo never leaves the device. Everything runs locally: no
API key, no network call at inference time.

**There is no labelled real data yet.** The platform trains, calibrates and measures itself
on deterministic synthetic plates, and every number below says so: synthetic results are not
real-world accuracy.

<!-- BEGIN RENDER ocr-benchmark-status -->
**OCR accuracy is not benchmarked on real data.** No labelled real evaluation set exists yet, so no real-world accuracy figure is claimed. `docs/insert_your_own_data.md` explains where real photos and labels go.
<!-- END RENDER ocr-benchmark-status -->

```console
$ uv run plate read samples/car.jpg
$ just demo        # synthetic data, a small evaluation, the whole stack, one synthetic read
```

## Contents

- [Why it is built this way](#why-it-is-built-this-way)
- [Architecture](#architecture)
- [How a read works](#how-a-read-works)
- [Results](#results)
- [Run it](#run-it)
- [Insert your own data](#insert-your-own-data)
- [What changes once real data arrives](#what-changes-once-real-data-arrives)
- [Honesty and limitations](#honesty-and-limitations)
- [The original reader](#the-original-reader)
- [Development](#development)
- [Credits and licence](#credits-and-licence)

## Why it is built this way

- **Plates have a grammar, so the reader should know it.** A standard plate is one to five
  digits, one of six Arabic letters and a one- or two-digit region; a temporary plate is
  digits followed by `WW`. The formats are compiled into one minimal automaton
  ([`plate_reader/grammar.py`](plate_reader/grammar.py)), and the recogniser's beam search
  only extends prefixes the automaton accepts, so it cannot return an impossible plate.
- **A confidence is only useful if it is calibrated.** The CRNN's posterior over plates is
  temperature-scaled on a held-out split, and every read carries a split-conformal
  prediction set: the plates that cannot be ruled out at the stated level. A set with more
  than one plate, or an empty one, is the system saying it does not know, and the read goes
  to review instead of being trusted.
- **Several photos beat one.** Views are fused in probability space (the product of the
  per-view posteriors is Bayes' rule for independent views), each number of fused views has
  its own conformal threshold, and every character of the fused read gets its own
  posterior.
- **No real data is no excuse for no measurement.** A seeded generator renders plates with
  open-licensed fonts and documented degradations; every split has its own seed; every
  metric has a bootstrap interval; a heavier pseudo-real preset stands in for the
  sim-to-real gap; and `data/` is a documented placeholder with a validator, ready for real
  photos.
- **Two runtimes, one answer.** The browser runtime is a TypeScript port of the Python
  pipeline's image operations, decoders and fusion; CI fails when it disagrees with the
  Python pipeline on the committed fixtures.

## Architecture

```mermaid
flowchart LR
  subgraph read["one read: 1 to 10 photos of one car"]
    P[photos] --> D["detector<br/>YOLOv10n, ONNX"]
    D --> C["plate crops"]
    C --> R["CRNN + CTC<br/>grammar-constrained beam"]
    R --> T["temperature-scaled<br/>posterior per view"]
    T --> F["probabilistic fusion<br/>per-character posteriors"]
    F --> S["conformal set<br/>threshold per number of views"]
  end
  S --> Q{"single plate and<br/>confident?"}
  Q -- yes --> L[(read log)]
  Q -- no --> V["review queue"]
  V --> E["data/ocr/train<br/>labelled crops"]
  E --> FT["fine-tune and recalibrate"]
  FT -.-> R
```

```mermaid
flowchart LR
  B["browser: Vue console<br/>(server or in-browser mode)"] -->|/api| N[nginx :5174]
  N --> A["API :8100<br/>FastAPI, ONNX Runtime"]
  A --> PG[(PostgreSQL :5433)]
  A --> RD[(Redis :6380)]
  RD --> W["worker<br/>folders and videos"]
  W --> PG
  A --> O["OpenTelemetry collector"]
  W --> O
  O --> PR["Prometheus :9100"]
  O -.->|tracing profile| TP["Tempo"]
  PR --> G["Grafana :3100"]
  TP --> G
```

The packages: [`plate_reader`](plate_reader) (grammar, synthetic generator, evaluation
harness, CRNN, calibration and conformal sets, fusion, pipeline, training, the `plate`
command line), [`services/api`](services/api) (the service, its database, jobs and review
queue) and [`apps/dashboard`](apps/dashboard) (the console and the in-browser runtime).
Decisions are recorded as ADRs in [`docs/adr`](docs/adr).

## How a read works

1. **Detect.** The YOLOv10n detector (ONNX, the NMS-free one-to-one head) finds plate boxes
   in each letterboxed photo; boxes are padded, cropped and de-duplicated, and each photo
   contributes its most confident plate.
2. **Read.** The CRNN (a residual CNN, a bidirectional LSTM and CTC) turns the grey crop into
   per-frame class scores; a prefix beam search that carries the grammar automaton's state
   keeps only viable plate prefixes and returns grammar-valid strings with their summed
   alignment probabilities.
3. **Calibrate.** One temperature, fitted by golden-section search on the negative
   log-likelihood of the true plate under the reported posterior, turns the beam into a
   calibrated distribution over plates.
4. **Fuse.** Every view's distribution is renormalised over the union of candidates with a
   floor and the views are multiplied (log opinion pooling), with exactly rounded sums so the
   order of the photos never matters; each character of the winner gets a posterior from
   aligning every candidate to it.
5. **Certify.** The conformal set keeps every candidate whose nonconformity (the probability
   mass of the other candidates) is under the threshold calibrated for that number of
   proposing views. The service serves sets at the level `PLATE_ALPHA` sets.
6. **Review.** A read whose set is not a single plate, or whose confidence is under
   `PLATE_REVIEW_THRESHOLD`, joins the review queue; a confirmed or corrected read exports
   its crops and label in the `data/ocr/train` layout, which `plate train crnn` fine-tunes on.

The equations, their assumptions and their tests are in
[`docs/methods/fusion.md`](docs/methods/fusion.md) and the
[model card](docs/model_card.md); the console's Methods page typesets them.

## Results

Every number in this section is rendered by `uv run plate docs render` from
[`docs/training_results.csv`](docs/training_results.csv) and `results/*.json`;
`uv run plate docs check` fails if a number is edited by hand or drifts from its source.

### Detection model

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

Full per-epoch metrics are in [`docs/training_results.csv`](docs/training_results.csv). On
synthetic street scenes, rendered from `results/eval_detector_synthetic.json`:

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

### Recognisers on synthetic plates

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

### The CRNN: training and calibration

<!-- BEGIN RENDER crnn-training -->
`models/crnn.onnx` (version `5348143705d4`, 5.8 MB, 1440051 parameters): trained on synthetic crops only, 24 epochs of 20000 freshly generated crops each on `cuda`, in 1139.4 s. The kept epoch is 18, chosen by greedy exact match on the synthetic validation split (0.995). Fine-tuned on real data: no. Augmentation: the generator's default degradation bounds. Synthetic results are not real-world accuracy.
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

Rendered from `results/eval_views.json`; the method and its properties are in
[`docs/methods/fusion.md`](docs/methods/fusion.md).

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

Calibration and conformal sets of the fused read (each number of views has its own threshold, fitted on separate synthetic multi-view sets; see `results/calibration_fused.json`):

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
| crnn-beam | probabilistic | 1 | 0.010 [0.003, 0.018] | 0.930 [0.895, 0.960] | 0.930 [0.895, 0.960] |
| crnn-beam | probabilistic | 5 | 0.000 [0.000, 0.000] | 0.900 [0.855, 0.940] | 0.900 [0.855, 0.940] |
| crnn-beam | probabilistic_weighted | 1 | 0.033 [0.024, 0.051] | 0.335 [0.270, 0.400] | 0.335 [0.270, 0.400] |
| crnn-beam | probabilistic_weighted | 5 | 0.000 [0.000, 0.000] | 0.250 [0.190, 0.305] | 0.250 [0.190, 0.305] |
<!-- END RENDER fusion-comparison -->

### The pseudo-real stand-in

A heavier augmentation preset stands in for the gap between synthetic and real photos until
real labelled data exists. Rendered from `results/eval_pseudo_real.json`. The console's
Models page draws the gap per recogniser, and `plate sweep` searches the augmentation
strengths that narrow it; its best configuration was then trained in full and compared
with the shipped weights (both in the [model card](docs/model_card.md)).

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

## Run it

Python 3.12 managed by [uv](https://docs.astral.sh/uv/), Node 20 or newer for the console,
Docker for the stack, and [just](https://github.com/casey/just) for the recipes. On Windows
the lock installs a CUDA 12.6 build of PyTorch, on Linux a CPU build; the service and the
worker are torch-free (ONNX Runtime).

```bash
git clone https://github.com/storm2121/Detectionx5.git
cd Detectionx5
just setup             # .venv with every dependency group, git hooks
just demo              # synthetic data, a small evaluation, docker compose up, one synthetic read
```

`docker compose up --build -d` starts the API, the worker, Redis, PostgreSQL, the
OpenTelemetry collector, Prometheus, Grafana and the console;
`docker compose --profile tracing up --build -d` adds Tempo as the trace store. Host ports
are chosen so the stack does not clash with other projects on the same machine:

| Service | Host port |
|---|---|
| Console (nginx forwards `/api` to the API) | 5174 |
| API (`services.api.main:app`) | 8100 |
| PostgreSQL | 5433 |
| Redis | 6380 |
| Prometheus | 9100 |
| Grafana (dashboard "DetectionX5 plate service") | 3100 |
| OpenTelemetry collector | 4319 (gRPC), 4320 (HTTP) |

Without Docker, `just api` serves the API on port 8100 with SQLite under `storage/`,
`just worker` runs a job worker against Redis on port 6380, and `just dashboard` serves the
console with Vite on port 5174.

**The console** (http://localhost:5174): Read (drop photos or try three synthetic photos of
one car; boxes, fields, calibrated confidence, conformal set, per-view hypotheses, the fusion
table, the character heatmap; server or in-browser mode with a parity indicator), Jobs
(folders and videos with live progress), Review queue (confirm, correct, export),
Evaluation (metrics with intervals, reliability diagrams, letter confusions, fusion by
number of views, coverage), Models (active models, thresholds, the registry, the training
curve, the sim-to-real gap, the augmentation sweep), Methods (the equations) and Browser
parity. Light and dark themes, phone width, axe-checked.

**The service:**

| Endpoint | Purpose |
|---|---|
| `POST /read` | one to ten photos of one car: plate, fields, calibrated confidence, conformal set, per-view hypotheses, per-character posteriors, model version; `detect=false` reads photos as crops |
| `GET /reads`, `GET /reads/{id}` | the read log |
| `GET /review/queue`, `POST /review/{id}`, `POST /review/export` | reads to review; corrections export to `data/ocr/train` |
| `POST /jobs`, `POST /jobs/upload`, `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/events` | folders and videos in the background (RQ on Redis), IoU tracking and per-track fusion, progress as Server-Sent Events |
| `GET /results`, `GET /results/{name}` | the committed evaluation results the console renders |
| `GET /models`, `GET /health`, `GET /metrics` | the registry and the loaded models, health, Prometheus metrics |

**The command line** (`uv run plate --help`):

| Command | What it does |
|---|---|
| `plate read PHOTO...` | read photos with the original reader (EasyOCR) |
| `plate synth crops / views / scenes / pseudo-real` | write deterministic synthetic sets |
| `plate eval --set synthetic / pseudo_real / views / data` | evaluate recognisers with bootstrap intervals |
| `plate eval-detector --data DETECTOR_YAML` | detector precision, recall and mAP through Ultralytics validation |
| `plate train crnn / calibrate / calibrate-fused / detector` | train and calibrate |
| `plate export onnx / detector / fixtures / web` | export models, parity fixtures and the browser's assets |
| `plate sweep` | search augmentation strengths against the pseudo-real set |
| `plate compare-crnn --old A.onnx --new B.onnx` | two CRNNs on the same crops, paired, with the adoption rule |
| `plate registry promote / list` | the model registry |
| `plate data validate / init` | check or create the real-data layout |
| `plate docs render / check` | render and check every documented number |

## Insert your own data

Real photos and labels go under `data/` in a fixed layout (detector images and YOLO
labels; OCR crops with a `crop_path,plate_text,format` CSV), and `uv run plate data
validate` checks it before anything trains. The step-by-step guide is
[`docs/insert_your_own_data.md`](docs/insert_your_own_data.md); the data card
([`docs/data_card.md`](docs/data_card.md)) lists what the data encodes. Real photos stay out
of git: a pre-commit check refuses images, videos and large CSVs under `data/`.

## What changes once real data arrives

- `uv run plate eval --set data` measures every recogniser on the real test split; the
  console and the docs then show real results next to the synthetic ones, and the
  statement that OCR accuracy is not benchmarked on real data can go.
- `plate train crnn` fine-tunes the CRNN on `data/ocr/train`, and the review queue's exports
  keep adding to that split.
- The temperature and every conformal threshold (one view, and each number of fused views)
  are refitted on real calibration splits: thresholds hold only for images exchangeable
  with the split they were fitted on.
- The detector is measured on real photos (`plate eval-detector --data data/detector.yaml`)
  and, if need be, fine-tuned (`plate train detector`); its current real-photo figures come
  from its own validation split, and its only independent ones from synthetic scenes.
- The augmentation sweep's objective moves from the pseudo-real tuning split to a real
  validation split, and the pseudo-real set becomes a robustness check instead of the
  stand-in for the real world.

## Honesty and limitations

- No real labelled evaluation exists: every recogniser metric, confidence and threshold here
  comes from synthetic data, and synthetic results are not real-world accuracy. The
  pseudo-real set is synthetic too.
- The detector's real-photo figures come from its own validation split, and its other
  figures from one pass over procedural street scenes; neither has an interval.
- The fonts approximate plate lettering; backgrounds are procedural; the generator draws no
  country band, dealer or damaged plates.
- Temporary plates are assumed to carry one to six digits until the range is confirmed.
- A conformal guarantee holds under exchangeability only; on images unlike the calibration
  split (the pseudo-real set shows how unlike) coverage drops, which is the warning it is
  meant to give.
- Only the six letters `أ ب د ه و ط` are accepted; other series are rejected by design.
- The original EasyOCR reader stays as the baseline and for the legacy entry points; it is
  much weaker than the CRNN on every synthetic set.

## The original reader

The project started as an EasyOCR reader: it finds the plate's two separator bars (the only
tall, very narrow marks on the plate), cuts the plate into its three fields, and reads each
field with the EasyOCR model suited to it, because reading the whole plate as one line turns
the bars into characters. That path is kept, behind the same shims as before:

```bash
python cli.py samples/car.jpg                 # read one image
python cli.py front.jpg side.jpg rear.jpg     # several photos of one car
python cli.py samples/car.jpg --json          # machine-readable output
python gui.py                                 # the desktop app
uvicorn api:app --host 127.0.0.1 --port 8000  # the original HTTP API
```

```python
from plate_reader import read_images

result = read_images(["samples/car.jpg"])
print(result.text)  # '24830-ب-1'
```

`read_images` fuses with the original vote unless every view is calibrated (ADR 0009).
EasyOCR downloads its recognition models the first time it runs; that is the only network
access the project makes.

## Development

```bash
just check            # ruff, mypy --strict, the repository guards, the console's checks,
                      # pytest with the coverage gate, plate docs check, plate data validate
just dashboard-e2e    # Playwright smoke, accessibility and parity checks against the stack
```

CI runs lint and guards, mypy, the test suite with coverage, a small synthetic evaluation, the
console's lint, build, tests and Storybook, the browser parity test, the console's smoke test
against Compose, and the container builds. Every setting is a `PLATE_*` environment variable
([`plate_reader/settings.py`](plate_reader/settings.py) and
[`services/api/config.py`](services/api/config.py)).

```
plate_reader/           the library and the `plate` command line
  grammar.py            the plate formats as one minimal automaton
  synthetic/            deterministic synthetic plates, scenes and multi-view sets
  eval/                 evaluation harness, bootstrap intervals, reports
  crnn/                 CRNN, CTC decoders, calibration, conformal sets, ONNX runtime
  fusion.py             probabilistic fusion and the legacy vote
  pipeline.py           detect, read, fuse, certify
  training/             CRNN training and calibration, ONNX export, the sweep
services/api/           the service: reads, review, jobs, metrics, migrations
apps/dashboard/         the console and the in-browser runtime
models/                 the detector and the CRNN (ONNX and PyTorch) with metadata
results/                every committed metric, as JSON
data/                   the real-data placeholder
docs/                   ADRs, model and data cards, methods, guides
tests/                  the Python test suite and the fixtures shared with the console
```

## Credits and licence

- Detection architecture: [YOLOv10](https://github.com/THU-MIG/yolov10) (THU-MIG), AGPL-3.0
- Detector training data: a plate dataset plus photos from the firm's experts
- OCR baseline: [EasyOCR](https://github.com/JaidedAI/EasyOCR), Apache-2.0
- Synthetic-plate and console fonts: SIL Open Font License 1.1 (see
  `plate_reader/synthetic/fonts/`)

Licensed under **AGPL-3.0** (see [LICENSE](LICENSE)). This is required rather than chosen:
the fine-tuned weights derive from YOLOv10 and Ultralytics, which are AGPL-3.0, so anything
distributed from them inherits that licence.
