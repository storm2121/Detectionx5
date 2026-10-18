"""Augmentations with documented distributions.

Every operation draws its parameters from the sample's own ``numpy.random.Generator`` and
scales with one ``strength`` in ``[0, 1]``: at strength 0 a crop is clean, at strength 1
every operation can reach the bound in :class:`AugmentConfig`. Curriculum training raises
the strength range over epochs; the pseudo-real preset (:data:`PSEUDO_REAL`) pushes the
bounds further to stand in for the sim-to-real gap until real data exists.

Distributions (``s`` is the strength, ``U`` uniform, ``B`` a Bernoulli draw):

=====================  =====================================================================
perspective            each plate corner moves by ``U(-1, 1) * s * perspective * plate_h``
rotation               ``U(-1, 1) * s * rotation_deg`` degrees about the plate centre
scale                  plate size times ``1 + U(-1, 1) * s * scale_jitter``
brightness, contrast   offset ``U(-1, 1) * s * brightness``, gain ``1 + U(-1, 1) * s * contrast``
gamma                  exponent ``exp(U(-1, 1) * s * gamma)``
colour cast            per-channel gain ``1 + U(-1, 1) * s * colour_cast``
shadow                 ``B(s * shadow_prob)``: a half-plane darkened by ``U(0.3, 1) * shadow_depth``
dirt                   ``B(s * dirt_prob)``: up to ``s * dirt_blobs`` blobs, alpha ``U(0.25, 0.8)``
glare                  ``B(s * glare_prob)``: an elliptical highlight
occlusion              ``B(s * occlusion_prob)``: an edge occluder up to ``occlusion_frac`` of the plate
motion blur            ``B(0.5 * s)``: length ``1 + U(0, 1) * s * motion_blur_px * h / 64``
Gaussian blur          ``B(0.5 * s)``: sigma ``U(0, 1) * s * gaussian_sigma * h / 64``
resolution             downscale by ``U(1 - s * (1 - downscale), 1)`` and back
noise                  Gaussian, sigma ``U(0, 1) * s * noise_sigma`` (0-255 scale)
JPEG                   ``B(0.7)``: quality ``U(95 - s * (95 - jpeg_min_quality), 95)``
=====================  =====================================================================
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Final

import cv2
import numpy as np

from ..imaging import Image, as_u8


@dataclass(frozen=True)
class AugmentConfig:
    """Bounds reached at strength 1."""

    perspective: float = 0.10
    rotation_deg: float = 6.0
    scale_jitter: float = 0.08
    brightness: float = 0.30
    contrast: float = 0.40
    gamma: float = 0.35
    colour_cast: float = 0.12
    shadow_prob: float = 0.5
    shadow_depth: float = 0.55
    dirt_prob: float = 0.5
    dirt_blobs: int = 40
    glare_prob: float = 0.0
    occlusion_prob: float = 0.15
    occlusion_frac: float = 0.08
    motion_blur_px: float = 7.0
    gaussian_sigma: float = 1.4
    downscale: float = 0.55
    noise_sigma: float = 12.0
    jpeg_min_quality: int = 35

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT: Final = AugmentConfig()
PSEUDO_REAL: Final = replace(
    DEFAULT,
    perspective=0.16,
    rotation_deg=9.0,
    brightness=0.40,
    contrast=0.50,
    colour_cast=0.20,
    shadow_prob=0.8,
    shadow_depth=0.65,
    dirt_prob=0.8,
    dirt_blobs=80,
    glare_prob=0.4,
    occlusion_prob=0.3,
    occlusion_frac=0.10,
    motion_blur_px=10.0,
    gaussian_sigma=1.8,
    downscale=0.40,
    noise_sigma=18.0,
    jpeg_min_quality=20,
)


def _sym(rng: np.random.Generator) -> float:
    return float(rng.uniform(-1.0, 1.0))


def plate_quad(
    rng: np.random.Generator,
    rect: tuple[float, float, float, float],
    strength: float,
    config: AugmentConfig,
) -> tuple[np.ndarray, dict[str, float]]:
    """Destination corners (tl, tr, br, bl) for a plate occupying ``rect`` = (x, y, w, h)."""
    x, y, w, h = rect
    scale = 1.0 + _sym(rng) * strength * config.scale_jitter
    angle = _sym(rng) * strength * config.rotation_deg
    cx, cy = x + w / 2, y + h / 2
    half_w, half_h = w * scale / 2, h * scale / 2
    corners = np.array(
        [[-half_w, -half_h], [half_w, -half_h], [half_w, half_h], [-half_w, half_h]],
        dtype=np.float64,
    )
    jitter = rng.uniform(-1.0, 1.0, size=(4, 2)) * strength * config.perspective * h
    corners += jitter
    theta = math.radians(angle)
    rotation = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    corners = corners @ rotation.T + np.array([cx, cy])
    return corners.astype(np.float32), {"scale": scale, "angle_deg": angle}


def warp_onto(canvas: Image, plate: Image, quad: np.ndarray) -> Image:
    """Composite ``plate`` onto ``canvas`` so that its corners land on ``quad``.

    A transparent-border warp writes the plate's pixels over a copy of the canvas in one
    pass; the hard edge is softened by the later downscale, as a camera would.
    """
    h, w = plate.shape[:2]
    src = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, quad)
    out = canvas.copy()
    cv2.warpPerspective(
        plate,
        matrix,
        (canvas.shape[1], canvas.shape[0]),
        dst=out,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_TRANSPARENT,
    )
    return out


def photometric(
    image: Image, rng: np.random.Generator, strength: float, config: AugmentConfig
) -> tuple[Image, dict[str, float]]:
    brightness = _sym(rng) * strength * config.brightness
    contrast = 1.0 + _sym(rng) * strength * config.contrast
    gamma = math.exp(_sym(rng) * strength * config.gamma)
    cast = 1.0 + rng.uniform(-1.0, 1.0, size=3) * strength * config.colour_cast
    # The transform is pointwise per channel, so a 256-entry table per channel is exact.
    levels = np.arange(256, dtype=np.float64) / 255.0
    curve = (np.power(levels, gamma) - 0.5) * contrast + 0.5 + brightness
    table = np.stack([curve * c for c in cast], axis=-1)
    lut = (np.clip(table, 0.0, 1.0) * 255.0).round().astype(np.uint8).reshape(1, 256, 3)
    channels = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    out = as_u8(cv2.LUT(channels, lut))
    return out, {
        "brightness": brightness,
        "contrast": contrast,
        "gamma": gamma,
        "cast_b": float(cast[0]),
        "cast_g": float(cast[1]),
        "cast_r": float(cast[2]),
    }


def shadow(
    image: Image, rng: np.random.Generator, strength: float, config: AugmentConfig
) -> tuple[Image, dict[str, float]]:
    if rng.random() >= strength * config.shadow_prob:
        return image, {"shadow": 0.0}
    h, w = image.shape[:2]
    depth = float(rng.uniform(0.3, 1.0)) * config.shadow_depth
    angle = float(rng.uniform(0.0, 2.0 * math.pi))
    offset = float(rng.uniform(-0.4, 0.4))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    proj = ((xx / w - 0.5) * math.cos(angle) + (yy / h - 0.5) * math.sin(angle)) - offset
    softness = max(0.02, float(rng.uniform(0.02, 0.15)))
    mask = 1.0 / (1.0 + np.exp(-proj / softness))
    factor = 1.0 - depth * mask
    out = as_u8((image.astype(np.float32) * factor[..., None]).round().clip(0, 255))
    return out, {"shadow": depth}


def dirt(
    image: Image, rng: np.random.Generator, strength: float, config: AugmentConfig
) -> tuple[Image, dict[str, float]]:
    if rng.random() >= strength * config.dirt_prob:
        return image, {"dirt": 0.0}
    h, w = image.shape[:2]
    count = int(rng.integers(3, max(4, int(strength * config.dirt_blobs) + 1)))
    # All blobs go into one alpha mask and one colour layer, composited once.
    alpha = np.zeros((h, w), dtype=np.uint8)
    colour = np.zeros((h, w, 3), dtype=np.uint8)
    for _ in range(count):
        centre = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        radius = int(rng.integers(1, max(2, h // 14)))
        tint = (int(rng.integers(30, 90)), int(rng.integers(50, 110)), int(rng.integers(70, 140)))
        opacity = round(float(rng.uniform(0.25, 0.8)) * 255)
        cv2.circle(colour, centre, radius, tint, -1, lineType=cv2.LINE_AA)
        cv2.circle(alpha, centre, radius, opacity, -1, lineType=cv2.LINE_AA)
    a = (alpha.astype(np.float32) / 255.0)[..., None]
    out = image.astype(np.float32) * (1.0 - a) + colour.astype(np.float32) * a
    return as_u8(out.round().clip(0, 255)), {"dirt": float(count)}


def glare(
    image: Image, rng: np.random.Generator, strength: float, config: AugmentConfig
) -> tuple[Image, dict[str, float]]:
    if rng.random() >= strength * config.glare_prob:
        return image, {"glare": 0.0}
    h, w = image.shape[:2]
    cx, cy = float(rng.uniform(0.1, 0.9)) * w, float(rng.uniform(0.0, 1.0)) * h
    rx, ry = float(rng.uniform(0.1, 0.4)) * w, float(rng.uniform(0.2, 0.8)) * h
    intensity = float(rng.uniform(0.3, 0.8))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    blob = np.exp(-(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2))[..., None] * intensity
    out = image.astype(np.float32) * (1.0 - blob) + 255.0 * blob
    return as_u8(out.round().clip(0, 255)), {"glare": intensity}


def occlusion(
    image: Image,
    rng: np.random.Generator,
    strength: float,
    config: AugmentConfig,
    plate_box: tuple[int, int, int, int],
) -> tuple[Image, dict[str, float]]:
    """An object over one end of the plate: never more than ``occlusion_frac`` of its width."""
    if rng.random() >= strength * config.occlusion_prob:
        return image, {"occlusion": 0.0}
    x1, _, x2, _ = plate_box
    width = max(1, x2 - x1)
    frac = float(rng.uniform(0.3, 1.0)) * config.occlusion_frac
    cover = max(1, int(width * frac))
    out = image.copy()
    colour = tuple(int(v) for v in rng.integers(0, 120, size=3))
    if rng.random() < 0.5:
        out[:, max(0, x1 - cover) : x1 + cover] = colour
    else:
        out[:, x2 - cover : x2 + cover] = colour
    return out, {"occlusion": frac}


def blur(
    image: Image, rng: np.random.Generator, strength: float, config: AugmentConfig
) -> tuple[Image, dict[str, float]]:
    params = {"motion_px": 0.0, "sigma": 0.0}
    out = image
    # Bounds are defined for a 64-pixel-high crop and scale with the actual height.
    ref = image.shape[0] / 64.0
    if rng.random() < 0.5 * strength:
        length = 1.0 + float(rng.uniform(0.0, 1.0)) * strength * config.motion_blur_px * ref
        angle = float(rng.uniform(0.0, 180.0))
        size = max(3, math.ceil(length) | 1)
        kernel = np.zeros((size, size), dtype=np.float32)
        kernel[size // 2, :] = 1.0
        rot = cv2.getRotationMatrix2D((size / 2 - 0.5, size / 2 - 0.5), angle, 1.0)
        rotated = np.asarray(cv2.warpAffine(kernel, rot, (size, size)), dtype=np.float32)
        rotated /= max(float(rotated.sum()), 1e-6)
        out = as_u8(cv2.filter2D(out, -1, rotated))
        params["motion_px"] = length
    if rng.random() < 0.5 * strength:
        sigma = float(rng.uniform(0.0, 1.0)) * strength * config.gaussian_sigma * ref
        if sigma > 0.05:
            out = as_u8(cv2.GaussianBlur(out, (0, 0), sigmaX=sigma))
            params["sigma"] = sigma
    return out, params


def resolution(
    image: Image, rng: np.random.Generator, strength: float, config: AugmentConfig
) -> tuple[Image, dict[str, float]]:
    factor = float(rng.uniform(1.0 - strength * (1.0 - config.downscale), 1.0))
    if factor >= 0.98:
        return image, {"resolution": 1.0}
    h, w = image.shape[:2]
    small = cv2.resize(
        image, (max(8, round(w * factor)), max(4, round(h * factor))), interpolation=cv2.INTER_AREA
    )
    return as_u8(cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)), {"resolution": factor}


def noise(
    image: Image, rng: np.random.Generator, strength: float, config: AugmentConfig
) -> tuple[Image, dict[str, float]]:
    sigma = float(rng.uniform(0.0, 1.0)) * strength * config.noise_sigma
    if sigma < 0.5:
        return image, {"noise_sigma": 0.0}
    grain = rng.standard_normal(size=image.shape, dtype=np.float32) * np.float32(sigma)
    return as_u8((image.astype(np.float32) + grain).round().clip(0, 255)), {"noise_sigma": sigma}


def jpeg(
    image: Image, rng: np.random.Generator, strength: float, config: AugmentConfig
) -> tuple[Image, dict[str, float]]:
    if rng.random() >= 0.7:
        return image, {"jpeg_quality": 100.0}
    low = 95.0 - strength * (95.0 - config.jpeg_min_quality)
    quality = round(float(rng.uniform(low, 95.0)))
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:  # pragma: no cover - OpenCV always encodes uint8 BGR
        return image, {"jpeg_quality": 100.0}
    return as_u8(cv2.imdecode(encoded, cv2.IMREAD_COLOR)), {"jpeg_quality": float(quality)}


def sharpness(image: Image) -> float:
    """Variance of the Laplacian on the grey image: a cheap, label-free quality signal."""
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(grey, cv2.CV_64F).var())


__all__ = [
    "DEFAULT",
    "PSEUDO_REAL",
    "AugmentConfig",
    "blur",
    "dirt",
    "glare",
    "jpeg",
    "noise",
    "occlusion",
    "photometric",
    "plate_quad",
    "resolution",
    "shadow",
    "sharpness",
    "warp_onto",
]
