"""Training data for the CRNN: synthetic crops generated on the fly, plus optional real crops.

Sample ``i`` of the stream is generated from ``(train seed, i)``, and its epoch is
``i // epoch_size``; the curriculum maps the epoch to the augmentation strength range, so a
worker process needs nothing but the index to reproduce a sample. Every epoch draws fresh
indices, so the network never sees the same synthetic crop twice.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, Sampler

from ..crnn.charset import encode
from ..crnn.preprocess import preprocess
from ..normalize import parse_plate
from ..synthetic.augment import DEFAULT, AugmentConfig
from ..synthetic.generate import make_crop


@dataclass(frozen=True)
class Curriculum:
    """Strength upper bound rises linearly from ``start`` to 1 over a fraction of training."""

    epochs: int
    start: float = 0.3
    ramp_fraction: float = 0.6

    def upper(self, epoch: int) -> float:
        ramp = max(1.0, self.ramp_fraction * self.epochs)
        return float(min(1.0, self.start + (1.0 - self.start) * epoch / ramp))


Sample = tuple[torch.Tensor, list[int]]


class SyntheticCrops(Dataset[Sample]):
    def __init__(
        self,
        seed: int,
        epoch_size: int,
        curriculum: Curriculum,
        augment: AugmentConfig = DEFAULT,
    ) -> None:
        self.seed = seed
        self.epoch_size = epoch_size
        self.curriculum = curriculum
        self.augment = augment

    def __len__(self) -> int:
        return self.epoch_size * self.curriculum.epochs

    def __getitem__(self, index: int) -> Sample:
        epoch = index // self.epoch_size
        sample = make_crop(
            self.seed,
            index,
            strength_range=(0.0, self.curriculum.upper(epoch)),
            config=self.augment,
        )
        return torch.from_numpy(preprocess(sample.image)), encode(sample.tokens)


class LabelledCrops(Dataset[Sample]):
    """A ``crop_path,plate_text,format`` folder (``data/ocr/<split>``), for fine-tuning."""

    def __init__(self, labels_csv: Path) -> None:
        self.rows: list[tuple[Path, str]] = []
        with labels_csv.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                plate = parse_plate(row["plate_text"])
                if plate is None:
                    raise ValueError(f"{labels_csv}: invalid plate {row['plate_text']!r}")
                self.rows.append((labels_csv.parent / row["crop_path"], plate.tokens))

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> Sample:
        path, tokens = self.rows[index]
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"cannot read {path}")
        return torch.from_numpy(preprocess(np.asarray(image, dtype=np.uint8))), encode(tokens)


class EpochSampler(Sampler[int]):
    """Indices of one epoch's slice of the stream, in a seeded random order."""

    def __init__(self, epoch_size: int, seed: int) -> None:
        self.epoch_size = epoch_size
        self.seed = seed
        self.epoch = 0

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch

    def __len__(self) -> int:
        return self.epoch_size

    def __iter__(self) -> Iterator[int]:
        order = np.random.default_rng((self.seed, self.epoch)).permutation(self.epoch_size)
        offset = self.epoch * self.epoch_size
        return iter((offset + order).tolist())


def collate(batch: list[Sample]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Images ``(B, 1, H, W)``, concatenated targets, and target lengths for CTC."""
    images = torch.stack([image for image, _ in batch])
    lengths = torch.tensor([len(target) for _, target in batch], dtype=torch.long)
    targets = torch.tensor([t for _, target in batch for t in target], dtype=torch.long)
    return images, targets, lengths


__all__ = ["Curriculum", "EpochSampler", "LabelledCrops", "SyntheticCrops", "collate"]
