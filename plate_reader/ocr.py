"""Offline OCR backends.

The default backend is EasyOCR, which runs entirely on the local machine: no API key,
no network at inference time, no per-request cost.

Two separate recognisers are used rather than one bilingual one. EasyOCR's English
model reads the plate's digits far more reliably than its Arabic model does, while the
Arabic model is needed for the single letter. Pointing each one at the field it is good
at, with an alphabet restricted to what that field can legally contain, is what makes an
offline read viable here.

Backends are looked up by name through :func:`get_backend`, so an alternative engine can
be dropped in without touching the pipeline.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Protocol

from .grammar import DIGITS as GRAMMAR_DIGITS
from .grammar import LETTERS, MARK
from .imaging import Image
from .settings import OCR_LANGUAGES, get_settings

DIGITS = GRAMMAR_DIGITS
# ``W`` is included for the temporary "WW" series.
DIGIT_ALPHABET = DIGITS + MARK
LETTER_ALPHABET = LETTERS
ALLOWED_CHARACTERS = DIGITS + LETTERS + MARK


@dataclass(frozen=True)
class Reading:
    """One raw OCR hypothesis."""

    text: str
    confidence: float
    variant: str = ""


class OCRBackend(Protocol):
    """Minimal contract a backend has to satisfy."""

    name: str

    def read_digits(self, image: Image) -> list[Reading]: ...

    def read_letters(self, image: Image) -> list[Reading]: ...

    def read(self, image: Image, restrict: bool = True) -> list[Reading]: ...


class EasyOCRBackend:
    """Local OCR via EasyOCR. Models load lazily and are reused."""

    name = "easyocr"

    def __init__(self, use_gpu: bool | None = None) -> None:
        self.use_gpu = get_settings().gpu if use_gpu is None else use_gpu
        self._digit_reader: Any = None
        self._letter_reader: Any = None
        self._mixed_reader: Any = None

    # --- model loading -----------------------------------------------------
    @staticmethod
    def _import_easyocr() -> Any:
        try:
            return importlib.import_module("easyocr")
        except ImportError as exc:  # pragma: no cover - environment issue
            raise ImportError("EasyOCR is not installed. Run: uv sync (group ml)") from exc

    def _reader(self, languages: list[str]) -> Any:
        easyocr = self._import_easyocr()
        # Downloads the recognition models on first run, then caches them.
        return easyocr.Reader(languages, gpu=self.use_gpu, verbose=False)

    @property
    def digit_reader(self) -> Any:
        if self._digit_reader is None:
            self._digit_reader = self._reader(["en"])
        return self._digit_reader

    @property
    def letter_reader(self) -> Any:
        if self._letter_reader is None:
            self._letter_reader = self._reader(["ar"])
        return self._letter_reader

    @property
    def mixed_reader(self) -> Any:
        if self._mixed_reader is None:
            self._mixed_reader = self._reader(list(OCR_LANGUAGES))
        return self._mixed_reader

    def load_models(self) -> None:
        """Eagerly load every reader, reusing any that were already initialised."""
        for reader_name in ("digit_reader", "letter_reader", "mixed_reader"):
            getattr(self, reader_name)

    # --- reading -----------------------------------------------------------
    @staticmethod
    def _collect(reader: Any, image: Image, allowlist: str | None) -> list[Reading]:
        options: dict[str, Any] = {"detail": 1, "paragraph": False}
        if allowlist:
            options["allowlist"] = allowlist

        try:
            results = reader.readtext(image, **options)
        except Exception:
            # One unreadable variant must never abort the whole run.
            return []

        readings: list[Reading] = []
        for entry in results:
            if len(entry) < 3:
                continue
            text, confidence = entry[1], entry[2]
            if text and str(text).strip():
                readings.append(Reading(str(text).strip(), float(confidence)))
        return readings

    def read_digits(self, image: Image) -> list[Reading]:
        """Read a field that should contain only digits."""
        return self._collect(self.digit_reader, image, DIGIT_ALPHABET)

    def read_letters(self, image: Image) -> list[Reading]:
        """Read a field that should contain a single Arabic letter."""
        return self._collect(self.letter_reader, image, LETTER_ALPHABET)

    def read(self, image: Image, restrict: bool = True) -> list[Reading]:
        """Read a whole plate at once: the fallback when segmentation fails."""
        allowlist = ALLOWED_CHARACTERS if restrict else None
        return self._collect(self.mixed_reader, image, allowlist)


_BACKENDS: dict[str, type[EasyOCRBackend]] = {EasyOCRBackend.name: EasyOCRBackend}


def available_backends() -> list[str]:
    return sorted(_BACKENDS)


def get_backend(name: str = EasyOCRBackend.name, **kwargs: Any) -> OCRBackend:
    """Instantiate a backend by name."""
    try:
        factory = _BACKENDS[name]
    except KeyError:
        raise ValueError(
            f"Unknown OCR backend {name!r}. Available: {', '.join(available_backends())}"
        ) from None
    return factory(**kwargs)


__all__ = [
    "ALLOWED_CHARACTERS",
    "DIGITS",
    "DIGIT_ALPHABET",
    "LETTER_ALPHABET",
    "EasyOCRBackend",
    "OCRBackend",
    "Reading",
    "available_backends",
    "get_backend",
]
