# Data card

Status: first version (follow-up to M4, extended in M7). Synthetic results are not
real-world accuracy.

## What data the platform uses today

- **Synthetic plates** from `plate_reader/synthetic/`: standard and temporary plates
  rendered from the plate grammar with open-licensed fonts, composed onto procedural
  bodywork or street scenes and degraded by documented, strength-scaled augmentations
  (`plate_reader/synthetic/augment.py` lists every distribution). Every split has its own
  fixed seed (`plate_reader/synthetic/splits.py`), so training, validation, calibration,
  conformal, test, pseudo-real and multi-view sets never share a sample, and a seed
  reproduces every byte.
- **The pseudo-real set**: the same generator with a heavier augmentation preset. It is a
  stand-in for the gap between synthetic and real photos, labelled pseudo-real everywhere,
  and it is still synthetic.
- **The detector's training data**: the shipped detector was trained on a publicly
  available plate dataset released under CC BY 4.0, plus photographs from the firm's
  experts; that data is not in this repository.
- **Real data**: none. `data/` is a documented placeholder (`data/README.md`,
  `docs/insert_your_own_data.md`) checked by `plate data validate`.

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

The conformal thresholds, the temperature and every reported metric come from synthetic
splits. They describe the synthetic distribution only; real photos will need their own
calibration and evaluation, which `docs/insert_your_own_data.md` describes.

## Privacy

Licence plates identify people. Real photos and crops stay out of git (`.gitignore` and a
pre-commit check), the service stores crops only for the review queue, and the browser mode
reads plates without uploading the photo.
