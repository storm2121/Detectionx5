# data/ (placeholder)

This folder is a **placeholder until real data exists**. The repository ships only this
README, the folder layout (empty folders kept with `.gitkeep`) and `detector.yaml`. Real
photos, crops, labels and videos are ignored by git, and a pre-commit check refuses any
image, video, archive or CSV with more than 50 rows staged under `data/`.

Everything else in the platform (tests, CI, the demo, the dashboard numbers) runs on the
deterministic synthetic generator, and every number computed that way is labelled
synthetic: synthetic results are not real-world accuracy.

## Layout

```
data/
├── README.md
├── detector.yaml                      # Ultralytics dataset file (one class: LP)
├── detector/
│   ├── images/{train,val}/*.jpg|png   # full photos
│   └── labels/{train,val}/*.txt       # YOLO boxes, one per line: 0 cx cy w h (normalised)
├── ocr/
│   ├── train/labels.csv               # crop_path,plate_text,format
│   └── val/labels.csv
└── eval/
    └── labels.csv                     # image_path,plate_text,format,x1,y1,x2,y2
```

- `crop_path` and `image_path` are relative to the folder that holds the CSV.
- `plate_text` is the display spelling: `24830-ب-1` for standard plates, `72173 WW` for
  temporary ones. It must be accepted by the plate grammar (`plate_reader/grammar.py`).
- `format` is `standard` or `temporary` and must agree with `plate_text`.
- `x1,y1,x2,y2` in `eval/labels.csv` are integer pixel coordinates of the plate box; leave
  all four empty when the box is unknown (OCR-only evaluation).

## Validate

```bash
uv run plate data validate            # human-readable report; exit 1 on errors
uv run plate data validate --json     # machine-readable report
uv run plate data validate --strict   # warnings fail too
uv run plate data init                # recreate the empty skeleton
```

An empty layout is valid. See `docs/insert_your_own_data.md` for the full procedure and for
what changes in the platform once real data is present.
