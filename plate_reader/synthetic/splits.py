"""Fixed seeds for every synthetic split.

Each purpose has its own seed, and sample generators are seeded from ``(seed, kind,
index, view)``, so the splits are independent streams: no evaluation, calibration or
conformal sample can coincide with a training sample. Changing a value here changes every
number derived from that split, so the values are part of the results' provenance and are
recorded in each results JSON.
"""

from __future__ import annotations

from typing import Final, Literal

Split = Literal["train", "val", "calibration", "conformal", "test", "pseudo_real", "views"]

SPLIT_SEEDS: Final[dict[str, int]] = {
    "train": 1001,
    "val": 1002,
    "calibration": 1003,  # temperature scaling
    "conformal": 1004,  # conformal quantile
    "test": 1005,  # the `synthetic` evaluation set
    "pseudo_real": 1006,  # the `pseudo_real` evaluation set
    "views": 1007,  # multi-view sets for fusion
}


def seed_for(split: Split) -> int:
    return SPLIT_SEEDS[split]


__all__ = ["SPLIT_SEEDS", "Split", "seed_for"]
