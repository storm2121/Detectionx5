"""Sample-level generation: crops, scenes, multi-view sets (crops or whole street photos)
and the pseudo-real set.

Determinism: every sample owns a generator seeded from ``(seed, kind, index, view)``
through ``numpy.random.SeedSequence``, so sample ``i`` is the same whether it is generated
alone, in a batch, in a DataLoader worker or on another day, and two kinds never share a
stream. The rendering and augmentation code draws all randomness from that generator and
uses only deterministic OpenCV and Pillow operations, so a seed reproduces identical pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal

import cv2
import numpy as np

from ..grammar import GRAMMAR, STANDARD, TEMPORARY, to_display
from ..imaging import Image, as_u8
from . import augment as aug
from .backgrounds import PAINTS, bodywork, scene
from .render import PlateStyle, render_plate, sample_style

#: Bump when the output for a given seed changes; recorded in every manifest and result.
GENERATOR_VERSION: Final = "1"

Kind = Literal["crop", "scene", "views", "pseudo_real", "scene_views"]
KIND_CODES: Final[dict[str, int]] = {
    "crop": 1,
    "scene": 2,
    "views": 3,
    "pseudo_real": 4,
    "scene_views": 5,
}

#: Fraction of temporary (WW) plates; they are rarer on the road than standard plates.
TEMPORARY_FRACTION: Final = 0.25
#: Output crop heights, in pixels, for crops and views (detector crops are small).
CROP_HEIGHT: Final = (28, 96)
PSEUDO_REAL_CROP_HEIGHT: Final = (20, 48)
#: Bounds every generated crop satisfies (the hypothesis invariants check them).
MIN_SIZE: Final = (16, 48)  # (height, width)
MAX_SIZE: Final = (160, 720)


def sample_rng(seed: int, kind: Kind, index: int, view: int = 0) -> np.random.Generator:
    return np.random.default_rng(
        np.random.SeedSequence(entropy=seed, spawn_key=(KIND_CODES[kind], index, view))
    )


@dataclass(frozen=True)
class CropSample:
    image: Image  # BGR
    tokens: str
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return to_display(self.tokens)

    @property
    def format(self) -> str:
        return GRAMMAR.format_of(self.tokens) or "unknown"


@dataclass(frozen=True)
class SceneSample:
    image: Image  # BGR
    plates: tuple[tuple[str, tuple[int, int, int, int]], ...]  # (tokens, x1, y1, x2, y2)
    meta: dict[str, Any] = field(default_factory=dict)


def _choose_tokens(rng: np.random.Generator, temporary_fraction: float) -> str:
    fmt = TEMPORARY if rng.random() < temporary_fraction else STANDARD
    return GRAMMAR.random_tokens(rng, fmt)


def _to_bgr(rgb: Image) -> Image:
    return as_u8(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def compose_crop(
    plate_bgr: Image,
    rng: np.random.Generator,
    strength: float,
    config: aug.AugmentConfig,
    height_range: tuple[int, int],
) -> tuple[Image, dict[str, Any]]:
    """Put a rendered plate on bodywork as a detector crop would see it, then degrade it."""
    out_h = int(rng.integers(height_range[0], height_range[1] + 1))
    pad_x = float(rng.uniform(0.04, 0.14))
    pad_y = float(rng.uniform(0.10, 0.35))
    work_h = plate_bgr.shape[0] * (1 + 2 * pad_y)
    # Compose at about twice the output resolution: enough for clean edges, far cheaper.
    scale = min(1.0, 2.0 * out_h / work_h)
    ph = max(4, round(plate_bgr.shape[0] * scale))
    pw = max(8, round(plate_bgr.shape[1] * scale))
    plate = as_u8(cv2.resize(plate_bgr, (pw, ph), interpolation=cv2.INTER_AREA))
    cw, ch = round(pw * (1 + 2 * pad_x)), round(ph * (1 + 2 * pad_y))
    canvas = bodywork(rng, ch, cw)
    rect = (pw * pad_x, ph * pad_y, float(pw), float(ph))
    quad, geo = aug.plate_quad(rng, rect, strength, config)
    canvas = aug.warp_onto(canvas, plate, quad)
    x1, y1 = (int(v) for v in np.floor(quad.min(axis=0)).clip(0))
    x2, y2 = int(min(cw, np.ceil(quad[:, 0].max()))), int(min(ch, np.ceil(quad[:, 1].max())))

    meta: dict[str, Any] = {"strength": strength, **geo}
    # Degrade at output resolution: cheaper, and blur and noise bounds are defined there.
    out_w = max(MIN_SIZE[1], round(cw * out_h / ch))
    sx, sy = out_w / cw, out_h / ch
    box = (int(x1 * sx), int(y1 * sy), int(np.ceil(x2 * sx)), int(np.ceil(y2 * sy)))
    image = as_u8(cv2.resize(canvas, (out_w, out_h), interpolation=cv2.INTER_AREA))
    image, p = aug.photometric(image, rng, strength, config)
    meta.update(p)
    for op in (aug.shadow, aug.dirt, aug.glare):
        image, p = op(image, rng, strength, config)
        meta.update(p)
    image, p = aug.occlusion(image, rng, strength, config, box)
    meta.update(p)
    image, p = aug.blur(image, rng, strength, config)
    meta.update(p)
    for op in (aug.resolution, aug.noise, aug.jpeg):
        image, p = op(image, rng, strength, config)
        meta.update(p)
    meta["sharpness"] = aug.sharpness(image)
    return image, meta


def make_crop(
    seed: int,
    index: int,
    *,
    strength: float | None = None,
    strength_range: tuple[float, float] = (0.0, 1.0),
    config: aug.AugmentConfig = aug.DEFAULT,
    temporary_fraction: float = TEMPORARY_FRACTION,
    kind: Kind = "crop",
    tokens: str | None = None,
    style: PlateStyle | None = None,
    view: int = 0,
    height_range: tuple[int, int] = CROP_HEIGHT,
) -> CropSample:
    """One labelled plate crop; ``tokens`` and ``style`` pin the plate (multi-view sets)."""
    rng = sample_rng(seed, kind, index, view)
    if tokens is None:
        tokens = _choose_tokens(rng, temporary_fraction)
    if style is None:
        style = sample_style(rng)
    s = float(rng.uniform(*strength_range)) if strength is None else float(strength)
    rendered = render_plate(tokens, style)
    image, meta = compose_crop(_to_bgr(rendered.image), rng, s, config, height_range)
    meta.update({"seed": seed, "index": index, "view": view, "kind": kind})
    return CropSample(image=image, tokens=tokens, meta=meta)


def make_pseudo_real(seed: int, index: int) -> CropSample:
    """Heavily augmented crop standing in for real photos (always labelled pseudo-real)."""
    return make_crop(
        seed,
        index,
        strength_range=(0.75, 1.0),
        config=aug.PSEUDO_REAL,
        kind="pseudo_real",
        height_range=PSEUDO_REAL_CROP_HEIGHT,
    )


def make_views(
    seed: int,
    index: int,
    k: int,
    *,
    strength_range: tuple[float, float] = (0.2, 1.0),
    config: aug.AugmentConfig = aug.DEFAULT,
) -> list[CropSample]:
    """``k`` photos of one plate: same text and paint, independent viewing conditions."""
    rng = sample_rng(seed, "views", index, 0)
    tokens = _choose_tokens(rng, TEMPORARY_FRACTION)
    style = sample_style(rng)
    return [
        make_crop(
            seed,
            index,
            strength_range=strength_range,
            config=config,
            kind="views",
            tokens=tokens,
            style=style,
            view=view + 1,
        )
        for view in range(k)
    ]


def make_scene(
    seed: int,
    index: int,
    *,
    size: tuple[int, int] = (480, 640),
    strength_range: tuple[float, float] = (0.0, 0.6),
    config: aug.AugmentConfig = aug.DEFAULT,
    empty_fraction: float = 0.1,
    tokens: str | None = None,
    style: PlateStyle | None = None,
    paint: int | None = None,
    kind: Kind = "scene",
    view: int = 0,
) -> SceneSample:
    """A procedural street scene with zero or one plate and its YOLO box.

    With ``tokens`` (and ``style`` and ``paint``) the scene always shows that plate on a car
    of that colour: one photo of a car that :func:`make_scene_views` photographs again.
    """
    rng = sample_rng(seed, kind, index, view)
    h, w = size
    layout = scene(rng, h, w, paint=paint)
    image = layout.image
    strength = float(rng.uniform(*strength_range))
    plates: list[tuple[str, tuple[int, int, int, int]]] = []
    if tokens is not None or rng.random() >= empty_fraction:
        if tokens is None:
            tokens = _choose_tokens(rng, TEMPORARY_FRACTION)
        if style is None:
            style = sample_style(rng)
        plate = _to_bgr(render_plate(tokens, style).image)
        pw = layout.plate_width
        ph = pw * plate.shape[0] / plate.shape[1]
        cx, cy = layout.plate_centre
        rect = (cx - pw / 2, cy - ph / 2, pw, ph)
        quad, _ = aug.plate_quad(rng, rect, strength, config)
        quad[:, 0] = quad[:, 0].clip(0, w - 1)
        quad[:, 1] = quad[:, 1].clip(0, h - 1)
        image = aug.warp_onto(image, plate, quad)
        x1, y1 = (int(v) for v in np.floor(quad.min(axis=0)))
        x2, y2 = (int(v) for v in np.ceil(quad.max(axis=0)))
        plates.append((tokens, (x1, y1, min(w, x2), min(h, y2))))
    image, photo = aug.photometric(image, rng, strength, config)
    meta: dict[str, Any] = dict(photo)
    image, p = aug.blur(image, rng, strength * 0.5, config)
    meta.update(p)
    image, p = aug.noise(image, rng, strength, config)
    meta.update(p)
    image, p = aug.jpeg(image, rng, strength, config)
    meta.update(p)
    meta.update({"seed": seed, "index": index, "kind": kind, "strength": strength})
    if view:
        meta["view"] = view
    return SceneSample(image=image, plates=tuple(plates), meta=meta)


def make_scene_views(
    seed: int,
    index: int,
    k: int,
    *,
    size: tuple[int, int] = (480, 640),
    strength_range: tuple[float, float] = (0.0, 0.6),
    config: aug.AugmentConfig = aug.DEFAULT,
) -> list[SceneSample]:
    """``k`` street photos of one car: the same plate, plate style and paint; every photo
    has its own framing, background, light and degradations.
    """
    rng = sample_rng(seed, "scene_views", index, 0)
    tokens = _choose_tokens(rng, TEMPORARY_FRACTION)
    style = sample_style(rng)
    paint = int(rng.integers(0, len(PAINTS)))
    return [
        make_scene(
            seed,
            index,
            size=size,
            strength_range=strength_range,
            config=config,
            tokens=tokens,
            style=style,
            paint=paint,
            kind="scene_views",
            view=view + 1,
        )
        for view in range(k)
    ]


__all__ = [
    "CROP_HEIGHT",
    "GENERATOR_VERSION",
    "KIND_CODES",
    "MAX_SIZE",
    "MIN_SIZE",
    "PSEUDO_REAL_CROP_HEIGHT",
    "TEMPORARY_FRACTION",
    "CropSample",
    "SceneSample",
    "compose_crop",
    "make_crop",
    "make_pseudo_real",
    "make_scene",
    "make_scene_views",
    "make_views",
    "sample_rng",
]
