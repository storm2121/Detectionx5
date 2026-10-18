"""Procedural backgrounds: car bodywork around a crop, and whole scenes for the detector.

Backgrounds are generated, never photographed, so no real vehicle enters the repository
(AGENT_RULES §1.4). They only need the statistics that matter to a plate reader: a paint
colour around the plate, gradients, low-frequency texture and occasional edges.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np

from ..imaging import Image, as_u8

# BGR paint colours common on cars.
PAINTS: Final[tuple[tuple[int, int, int], ...]] = (
    (235, 235, 235),
    (200, 200, 205),
    (40, 40, 45),
    (30, 30, 160),
    (140, 60, 30),
    (115, 110, 110),
    (140, 180, 200),
    (50, 90, 30),
    (20, 20, 20),
)


def _low_frequency(
    rng: np.random.Generator, h: int, w: int, cell: int, amplitude: float
) -> np.ndarray:
    grid = rng.normal(0.0, 1.0, size=(h // cell + 2, w // cell + 2)).astype(np.float32)
    return cv2.resize(grid, (w, h), interpolation=cv2.INTER_CUBIC) * amplitude


def bodywork(rng: np.random.Generator, h: int, w: int) -> Image:
    """A painted panel with a gradient, mottling and an optional bumper edge.

    The field is built at an eighth of the resolution and upsampled: paint varies slowly,
    and this keeps on-the-fly generation cheap.
    """
    paint = np.array(PAINTS[int(rng.integers(0, len(PAINTS)))], dtype=np.float32)
    paint += rng.uniform(-15, 15, size=3).astype(np.float32)
    sh, sw = max(2, h // 8), max(2, w // 8)
    rows = np.linspace(
        float(rng.uniform(0.7, 1.0)), float(rng.uniform(1.0, 1.2)), sh, dtype=np.float32
    )
    if rng.random() < 0.5:
        rows = rows[::-1]
    small = np.ones((sh, sw, 3), dtype=np.float32) * paint[None, None, :] * rows[:, None, None]
    small += rng.normal(0.0, 8.0, size=(sh, sw, 1)).astype(np.float32)
    image = as_u8(cv2.resize(small.clip(0, 255), (w, h), interpolation=cv2.INTER_LINEAR).round())
    if rng.random() < 0.5:
        edge = int(rng.integers(0, h))
        thickness = int(rng.integers(1, max(2, h // 8)))
        factor = float(rng.uniform(0.4, 0.8))
        image[edge : edge + thickness] = as_u8(image[edge : edge + thickness] * factor)
    return image


@dataclass(frozen=True)
class SceneLayout:
    image: Image
    plate_centre: tuple[float, float]
    plate_width: float  # the plate width the car's bumper suggests


def scene(rng: np.random.Generator, h: int, w: int) -> SceneLayout:
    """A road, a sky, buildings and a car seen from the front or back."""
    sky = np.array([rng.uniform(150, 240), rng.uniform(140, 220), rng.uniform(110, 200)])
    ground = np.array([rng.uniform(60, 120)] * 3) + rng.uniform(-10, 10, size=3)
    horizon = int(h * float(rng.uniform(0.35, 0.55)))
    image = np.zeros((h, w, 3), dtype=np.float32)
    image[:horizon] = sky
    image[horizon:] = ground
    for _ in range(int(rng.integers(2, 7))):
        bx = int(rng.integers(0, w))
        bw = int(rng.integers(w // 10, w // 3))
        bh = int(rng.integers(h // 10, max(h // 10 + 1, horizon)))
        colour = rng.uniform(70, 200, size=3)
        image[max(0, horizon - bh) : horizon, bx : bx + bw] = colour
    image += _low_frequency(rng, h, w, 24, 6.0)[..., None]

    car_w = int(w * float(rng.uniform(0.45, 0.8)))
    car_h = int(car_w * float(rng.uniform(0.45, 0.65)))
    car_x = int(rng.integers(0, max(1, w - car_w)))
    car_y = min(h - car_h, int(horizon + rng.uniform(-0.25, 0.15) * car_h))
    car_y = max(0, car_y)
    paint = np.array(PAINTS[int(rng.integers(0, len(PAINTS)))], dtype=np.float32)
    body = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(body, (car_x, car_y + car_h // 3), (car_x + car_w, car_y + car_h), 255, -1)
    roof = np.array(
        [
            [car_x + car_w // 6, car_y + car_h // 3],
            [car_x + car_w // 4, car_y],
            [car_x + 3 * car_w // 4, car_y],
            [car_x + 5 * car_w // 6, car_y + car_h // 3],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(body, [roof], 255)
    mask = (body > 0)[..., None]
    shade = rng.uniform(0.85, 1.1)
    image = np.where(mask, paint * shade, image)
    glass = np.array(
        [
            [car_x + car_w // 5, car_y + car_h // 3 - 2],
            [car_x + car_w // 4 + 4, car_y + 4],
            [car_x + 3 * car_w // 4 - 4, car_y + 4],
            [car_x + 4 * car_w // 5, car_y + car_h // 3 - 2],
        ],
        dtype=np.int32,
    )
    canvas = as_u8(image.round().clip(0, 255))
    cv2.fillPoly(canvas, [glass], tuple(int(v) for v in rng.uniform(20, 70, size=3)))
    wheel_r = max(3, car_h // 6)
    for wx in (car_x + car_w // 6, car_x + 5 * car_w // 6):
        cv2.circle(canvas, (wx, min(h - 1, car_y + car_h)), wheel_r, (20, 20, 20), -1)
    light_y = car_y + int(car_h * 0.5)
    for lx in (car_x + car_w // 10, car_x + 9 * car_w // 10 - car_w // 8):
        cv2.rectangle(
            canvas, (lx, light_y), (lx + car_w // 8, light_y + car_h // 10), (210, 230, 240), -1
        )
    centre = (car_x + car_w / 2, car_y + car_h * float(rng.uniform(0.68, 0.8)))
    plate_width = car_w * float(rng.uniform(0.2, 0.32))
    return SceneLayout(image=canvas, plate_centre=centre, plate_width=plate_width)


__all__ = ["PAINTS", "SceneLayout", "bodywork", "scene"]
