"""The bundled OFL fonts and a cached loader.

Fonts are looked up by key so a generated sample's metadata can record exactly which
typeface and weight drew it. Loading goes through an ``lru_cache`` because FreeType face
creation dominates rendering time when thousands of crops are generated on the fly; each
DataLoader worker process gets its own cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

from PIL import ImageFont

FONT_DIR: Final = Path(__file__).resolve().parent / "fonts"

Script = Literal["latin", "arabic"]


@dataclass(frozen=True)
class FontSpec:
    key: str
    path: str  # relative to FONT_DIR
    family: str
    script: Script
    weights: tuple[int, ...] = ()  # weight-axis values to sample (variable fonts only)
    licence: str = "OFL-1.1"


FONTS: Final[tuple[FontSpec, ...]] = (
    FontSpec(
        "barlow-condensed-semibold",
        "barlow-condensed/BarlowCondensed-SemiBold.ttf",
        "Barlow Condensed",
        "latin",
    ),
    FontSpec(
        "barlow-condensed-bold",
        "barlow-condensed/BarlowCondensed-Bold.ttf",
        "Barlow Condensed",
        "latin",
    ),
    FontSpec(
        "noto-kufi-arabic",
        "noto-kufi-arabic/NotoKufiArabic-VF.ttf",
        "Noto Kufi Arabic",
        "arabic",
        weights=(500, 600, 700, 800),
    ),
    FontSpec(
        "noto-naskh-arabic",
        "noto-naskh-arabic/NotoNaskhArabic-VF.ttf",
        "Noto Naskh Arabic",
        "arabic",
        weights=(500, 600, 700),
    ),
)
FONT_BY_KEY: Final = {spec.key: spec for spec in FONTS}
LATIN_FONTS: Final = tuple(spec for spec in FONTS if spec.script == "latin")
ARABIC_FONTS: Final = tuple(spec for spec in FONTS if spec.script == "arabic")


@lru_cache(maxsize=512)
def load_font(key: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    """A FreeType face at ``size`` pixels, set to ``weight`` on variable fonts."""
    spec = FONT_BY_KEY[key]
    font = ImageFont.truetype(str(FONT_DIR / spec.path), size)
    if weight is not None and spec.weights:
        font.set_variation_by_axes([weight])
    return font


__all__ = [
    "ARABIC_FONTS",
    "FONTS",
    "FONT_BY_KEY",
    "FONT_DIR",
    "LATIN_FONTS",
    "FontSpec",
    "load_font",
]
