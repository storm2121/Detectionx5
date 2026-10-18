"""Image type aliases and the narrow conversions OpenCV's stubs need.

OpenCV returns ``MatLike`` unions from almost every call. Converting once at the
boundary with :func:`as_u8` keeps the rest of the code on a single precise type
(``uint8`` arrays) without copying data that is already in that form.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

#: An 8-bit image: ``HxW`` greyscale or ``HxWx3`` BGR, as OpenCV produces them.
type Image = npt.NDArray[np.uint8]


def as_u8(array: Any) -> Image:
    """View ``array`` as a ``uint8`` image (no copy when it already is one)."""
    return np.asarray(array, dtype=np.uint8)


def as_i32(array: Any) -> npt.NDArray[np.int32]:
    return np.asarray(array, dtype=np.int32)


__all__ = ["Image", "as_i32", "as_u8"]
