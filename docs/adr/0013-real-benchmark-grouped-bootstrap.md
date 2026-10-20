# ADR 0013: the real benchmark resamples vehicles, reads photos end to end, and says what it is not

Status: accepted (executing agent, real-data benchmark pass, 2026-10-20). Deviates from
ARCHITECTURE §9 ("bootstrap CIs by image") and §3 (`data/eval/labels.csv` has seven columns).

## Context

A held-out split of street photos of vehicles, with YOLO boxes, is now labelled with plate
text under `data/eval` (private, gitignored). Building it showed four things that a
per-image benchmark would hide:

- Every photo of the split is an augmented copy of a camera photo (contrast, noise, a shift,
  a rotation, a horizontal flip or a vertical flip), and one camera photo can have several
  copies in the split. Several camera photos also show the same vehicle.
- Every camera photo of the split also has copies in the split the detector was trained on.
  The files were never used for training or selection, but the scenes were.
- A mirrored plate is not a real-world input: no camera produces one.
- Some plates cannot be read by a person (blur, glare, noise, a tow hitch in front of a
  digit) or are outside the grammar (foreign plates, two-row moped plates, a special series).

## Decision

- `data/eval/labels.csv` takes an optional eighth column, `group`. Rows that share a group
  are resampled together. The validator accepts the seven-column header or the eight-column
  one; a set without the column keeps the per-row bootstrap, unchanged.
- When a set carries groups, `Bootstrap` draws groups with replacement (a cluster
  bootstrap); `bootstrap.unit` is `group` and the set header records how many groups there
  are. For the street photos a group is a vehicle with every photo it appears in (the
  connected components of "same plate" and "same camera photo"), so neither the copies of one
  photo nor repeat photos of one car count as independent evidence.
- The set is built with the flips undone exactly (the photo and its boxes), so every plate
  reads the right way round; rotated and shifted copies stay as they are, because no exact
  inverse exists and each still shows a real plate. Plates nobody can read, and plates
  outside the grammar, are left out of the text labels and listed with the reason in a
  private `unresolved.csv`; the detector labels keep every valid box.
- `plate eval --set data --detect` reads each labelled photo end to end and ignores the
  labelled boxes: the most confident detection is read, as the service reads it, and a photo
  where the detector finds nothing counts as a read that returned nothing. The labelled boxes
  only decide which plate of a photo the read is scored against and whether the detection
  lies on a labelled plate. Results go to `results/eval_data_e2e.json`.
- A set may carry `data/eval/card.json`: counts and words that describe it (never a plate
  string); the harness copies it into the results, so the documents render the set's
  description instead of typing it.
- The detector's figures on this split are published with the overlap stated next to them:
  they are not an independent measurement of the detector.
- Neither the temperature nor any conformal threshold is refitted on this split, and nothing
  is fine-tuned on it: it is the reporting set. A separate real calibration split comes next.

## Consequences

The intervals are honest for the number of vehicles behind the photos, and wider than a
per-photo bootstrap would print. The recogniser figures are clean (it has only seen
synthetic plates); the end-to-end and detector figures carry the overlap caveat, and so does
the detector's own validation split, which shares camera photos with its training split in
the same way. Leaving unreadable plates out means the benchmark measures plates a person can
read; it does not count them as failures, and the count of plates left out is published.
