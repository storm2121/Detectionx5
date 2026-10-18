"""Render a clean Moroccan plate from a canonical token string.

Geometry follows the printed plate rather than a font sample: a white plate with a dark
rim, the serial digits, two tall separator bars around the Arabic letter, then the region
code; temporary plates print the digits and ``WW`` without bars. Every visual choice is a
field of :class:`PlateStyle`, sampled from documented ranges by :func:`sample_style`, so a
sample's metadata reproduces its appearance exactly.

Rendering happens at a fixed working height (:data:`WORK_HEIGHT` pixels, roughly one pixel
per millimetre of a real plate) and is downscaled later by the augmentation stage.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Final

import numpy as np
from PIL import Image as PILImage
from PIL import ImageDraw

from ..grammar import GRAMMAR, SEP
from ..imaging import Image
from .fonts import ARABIC_FONTS, LATIN_FONTS, load_font

WORK_HEIGHT: Final = 110
#: Real long plates are 520 x 110 mm; short variants exist, so the aspect is sampled.
ASPECT_RANGE: Final = (4.2, 4.9)


@dataclass(frozen=True)
class PlateStyle:
    """Everything that decides how one plate looks. Colours are RGB."""

    width: int
    height: int
    background: tuple[int, int, int]
    ink: tuple[int, int, int]
    rim: int
    corner_radius: int
    bolts: bool
    latin_font: str
    arabic_font: str
    arabic_weight: int
    text_height: float  # digit ink height as a fraction of plate height
    letter_scale: float  # Arabic font size relative to the digit font size
    spacing: float  # extra space between digits, fraction of the digit height
    bar_width: float  # separator width, fraction of plate height
    bar_height: float  # separator height, fraction of plate height
    gap: float  # space around a separator, fraction of plate height
    x_jitter: float  # horizontal offset of the text block, fraction of slack
    y_jitter: float  # vertical offset of the text block, fraction of plate height

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _uniform(rng: np.random.Generator, low: float, high: float) -> float:
    return float(rng.uniform(low, high))


def sample_style(rng: np.random.Generator) -> PlateStyle:
    """Sample a plate style; ranges are wide on purpose (domain randomisation)."""
    aspect = _uniform(rng, *ASPECT_RANGE)
    height = WORK_HEIGHT
    width = round(height * aspect)
    paper = int(rng.integers(225, 256))
    tint = rng.integers(-5, 6, size=3)
    background = tuple(int(np.clip(paper + t, 200, 255)) for t in tint)
    ink_level = int(rng.integers(0, 45))
    ink = (ink_level, ink_level, min(255, ink_level + int(rng.integers(0, 12))))
    arabic = ARABIC_FONTS[int(rng.integers(0, len(ARABIC_FONTS)))]
    return PlateStyle(
        width=width,
        height=height,
        background=(background[0], background[1], background[2]),
        ink=ink,
        rim=int(rng.integers(2, 6)),
        corner_radius=int(rng.integers(4, 14)),
        bolts=bool(rng.random() < 0.6),
        latin_font=LATIN_FONTS[int(rng.integers(0, len(LATIN_FONTS)))].key,
        arabic_font=arabic.key,
        arabic_weight=int(arabic.weights[int(rng.integers(0, len(arabic.weights)))]),
        text_height=_uniform(rng, 0.52, 0.68),
        letter_scale=_uniform(rng, 0.85, 1.10),
        spacing=_uniform(rng, 0.02, 0.10),
        bar_width=_uniform(rng, 0.035, 0.06),
        bar_height=_uniform(rng, 0.62, 0.80),
        gap=_uniform(rng, 0.10, 0.22),
        x_jitter=_uniform(rng, -0.5, 0.5),
        y_jitter=_uniform(rng, -0.03, 0.03),
    )


@lru_cache(maxsize=16384)
def _glyph_mask(text: str, font_key: str, size: int, weight: int | None) -> np.ndarray:
    """Tight ink mask (uint8, 0..255) of ``text`` in one font.

    Cached because the same glyph at the same integer size recurs constantly during
    on-the-fly generation; callers must treat the returned array as read-only.
    """
    font = load_font(font_key, size, weight)
    left, top, right, bottom = font.getbbox(text)
    width, height = max(1, math.ceil(right - left)), max(1, math.ceil(bottom - top))
    canvas = PILImage.new("L", (width + 4, height + 4), 0)
    ImageDraw.Draw(canvas).text((2 - left, 2 - top), text, font=font, fill=255)
    mask = np.asarray(canvas, dtype=np.uint8)
    rows, cols = np.nonzero(mask > 24)
    if rows.size == 0:
        return np.zeros((height, width), dtype=np.uint8)
    return mask[rows.min() : rows.max() + 1, cols.min() : cols.max() + 1]


def _digit_size(style: PlateStyle) -> int:
    # Digit cap height is about 0.72 of the font size for Barlow; solve for the size.
    return max(8, round(style.text_height * style.height / 0.72))


@dataclass(frozen=True)
class RenderedPlate:
    image: Image  # RGB, height x width x 3
    tokens: str
    boxes: tuple[tuple[str, tuple[int, int, int, int]], ...]  # (symbol, x1, y1, x2, y2)


def render_plate(tokens: str, style: PlateStyle) -> RenderedPlate:
    """Draw ``tokens`` (a grammar-valid canonical string) in ``style``."""
    split = GRAMMAR.segment(tokens)
    if split is None:
        raise ValueError(f"not a valid plate: {tokens!r}")
    fmt, fields = split
    h, w = style.height, style.width
    size = _digit_size(style)
    letter_size = max(8, round(size * style.letter_scale * 0.95))

    # (kind, symbol, mask) items laid out left to right.
    items: list[tuple[str, str, np.ndarray]] = []
    bar_w = max(2, round(style.bar_width * h))
    bar_h = max(4, round(style.bar_height * h))
    bar = np.full((bar_h, bar_w), 255, dtype=np.uint8)
    for name, value in fields.items():
        if name.startswith("sep"):
            if fmt.name == "standard":
                items.append(("bar", SEP, bar))
            else:
                items.append(("gap", SEP, np.zeros((1, round(style.gap * h * 1.5)), np.uint8)))
            continue
        for symbol in value:
            if name == "letter":
                mask = _glyph_mask(symbol, style.arabic_font, letter_size, style.arabic_weight)
            else:
                mask = _glyph_mask(symbol, style.latin_font, size, None)
            items.append(("glyph", symbol, mask))

    digit_h = int(max(m.shape[0] for k, s, m in items if k == "glyph" and s.isdigit()))
    spacing = round(style.spacing * digit_h)
    gap = round(style.gap * h)

    def advance(index: int) -> int:
        kind = items[index][0]
        nxt = items[index + 1][0] if index + 1 < len(items) else None
        if kind in ("bar", "gap") or nxt in ("bar", "gap"):
            return gap
        return spacing

    total = sum(m.shape[1] for _, _, m in items) + sum(advance(i) for i in range(len(items) - 1))
    margin = style.rim + round(0.06 * h)
    slack = w - 2 * margin - total
    scale = 1.0
    if slack < 0:
        # Too wide for this plate: shrink every item uniformly (condensing, as printers do).
        scale = (w - 2 * margin) / total
        slack = 0

    canvas = PILImage.new("RGB", (w, h), style.background)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (style.rim // 2, style.rim // 2, w - 1 - style.rim // 2, h - 1 - style.rim // 2),
        radius=style.corner_radius,
        outline=style.ink,
        width=style.rim,
    )
    if style.bolts:
        radius = max(2, round(0.045 * h))
        for cx in (round(0.035 * w) + radius, w - round(0.035 * w) - radius):
            if margin > 2 * radius:
                draw.ellipse(
                    (cx - radius, h // 2 - radius, cx + radius, h // 2 + radius),
                    fill=(150, 150, 150),
                    outline=(90, 90, 90),
                )

    ink_layer = np.zeros((h, w), dtype=np.uint8)
    x = margin + round(slack * (0.5 + style.x_jitter))
    centre_y = h / 2 + style.y_jitter * h
    boxes: list[tuple[str, tuple[int, int, int, int]]] = []
    for index, (kind, symbol, mask) in enumerate(items):
        if scale != 1.0:
            new_w = max(1, round(mask.shape[1] * scale))
            new_h = max(1, round(mask.shape[0] * (scale if kind != "bar" else 1.0)))
            mask = np.asarray(
                PILImage.fromarray(mask).resize((new_w, new_h), PILImage.Resampling.BILINEAR),
                dtype=np.uint8,
            )
        mh, mw = mask.shape
        if kind != "gap":
            y = round(centre_y - mh / 2)
            y0, y1 = max(0, y), min(h, y + mh)
            x0, x1 = max(0, x), min(w, x + mw)
            if y1 > y0 and x1 > x0:
                patch = mask[y0 - y : y1 - y, x0 - x : x1 - x]
                ink_layer[y0:y1, x0:x1] = np.maximum(ink_layer[y0:y1, x0:x1], patch)
            boxes.append((symbol, (x0, y0, x1, y1)))
        x += mw + (round(advance(index) * scale) if index < len(items) - 1 else 0)

    solid = PILImage.new("RGB", (w, h), style.ink)
    composed = PILImage.composite(solid, canvas, PILImage.fromarray(ink_layer, mode="L"))
    image = np.asarray(composed, dtype=np.uint8)
    return RenderedPlate(image=image, tokens=tokens, boxes=tuple(boxes))


__all__ = [
    "ASPECT_RANGE",
    "WORK_HEIGHT",
    "PlateStyle",
    "RenderedPlate",
    "render_plate",
    "sample_style",
]
