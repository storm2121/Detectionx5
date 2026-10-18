"""Deterministic synthetic Moroccan plates: crops, scenes, multi-view sets, pseudo-real.

The generator is how the platform runs, trains and measures itself with zero real data
(ADR 0002). Everything it produces is labelled synthetic; the pseudo-real set is a heavier
augmentation preset that stands in for the sim-to-real gap until real photos exist.
"""

from __future__ import annotations

from .augment import DEFAULT, PSEUDO_REAL, AugmentConfig
from .generate import (
    GENERATOR_VERSION,
    CropSample,
    SceneSample,
    make_crop,
    make_pseudo_real,
    make_scene,
    make_scene_views,
    make_views,
    sample_rng,
)
from .render import PlateStyle, render_plate, sample_style
from .writer import Manifest, encode_png, write_crops, write_scenes, write_views

__all__ = [
    "DEFAULT",
    "GENERATOR_VERSION",
    "PSEUDO_REAL",
    "AugmentConfig",
    "CropSample",
    "Manifest",
    "PlateStyle",
    "SceneSample",
    "encode_png",
    "make_crop",
    "make_pseudo_real",
    "make_scene",
    "make_scene_views",
    "make_views",
    "render_plate",
    "sample_rng",
    "sample_style",
    "write_crops",
    "write_scenes",
    "write_views",
]
