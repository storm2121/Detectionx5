"""Crop to model input: the one transform every runtime must reproduce exactly.

Grey conversion with OpenCV's weights, a plain resize to the fixed input size, and scaling
to ``[-1, 1]``. No aspect-preserving padding: it would add a data-dependent branch that the
TypeScript port would have to mirror, while the generator already randomises aspect ratio.
"""

from __future__ import annotations

from typing import Final

import cv2
import numpy as np
import numpy.typing as npt

from ..imaging import Image, as_u8

INPUT_HEIGHT: Final = 32
INPUT_WIDTH: Final = 160
MEAN: Final = 0.5
STD: Final = 0.5


def to_grey(image: Image) -> Image:
    if image.ndim == 2:
        return image
    return as_u8(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))


def preprocess(
    image: Image, height: int = INPUT_HEIGHT, width: int = INPUT_WIDTH
) -> npt.NDArray[np.float32]:
    """``(1, height, width)`` float32 in ``[-1, 1]`` from a BGR or grey uint8 crop."""
    grey = to_grey(image)
    shrinking = grey.shape[0] > height or grey.shape[1] > width
    resized = cv2.resize(
        grey, (width, height), interpolation=cv2.INTER_AREA if shrinking else cv2.INTER_LINEAR
    )
    scaled = np.asarray(resized, dtype=np.float32) / np.float32(255.0)
    return ((scaled - np.float32(MEAN)) / np.float32(STD))[None, :, :]


def batch(
    images: list[Image], height: int = INPUT_HEIGHT, width: int = INPUT_WIDTH
) -> npt.NDArray[np.float32]:
    """``(N, 1, height, width)`` float32 batch."""
    if not images:
        return np.zeros((0, 1, height, width), dtype=np.float32)
    return np.stack([preprocess(im, height, width) for im in images])


__all__ = ["INPUT_HEIGHT", "INPUT_WIDTH", "MEAN", "STD", "batch", "preprocess", "to_grey"]
