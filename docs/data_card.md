# Data card

Status: v2 (milestones M6 and M7; v1 was the follow-up to M4). Synthetic results are not
real-world accuracy.

## What data the platform uses today

- **A small private set of labelled real photos** under `data/eval` (gitignored and
  never committed), used for evaluation only: nothing is trained, calibrated or tuned
  on it. Its metrics, and only its metrics, are in `results/eval_data.json`.
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
- **Real data**: none. `data/` is a documented placeholder (`data/README.md`,
  `docs/insert_your_own_data.md`) checked by `plate data validate`.

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
only: on the real photos neither the confidence nor the sets hold, so real photos need
their own calibration, which `docs/insert_your_own_data.md` describes.

## Privacy

Licence plates identify people. Real photos and crops stay out of git (`.gitignore` and a
pre-commit check), the service stores crops only for the review queue, and the browser mode
reads plates without uploading the photo.
