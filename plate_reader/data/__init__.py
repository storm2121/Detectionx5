"""The real-data placeholder: its folder layout and the validator for it.

``data/`` stays empty in the repository until real photos and labels exist. Everything
else in the platform runs on synthetic data; this package is what makes the eventual real
data drop into a documented place and be checked before any number is computed from it.
"""

from __future__ import annotations

from .layout import DataLayout
from .validate import Issue, ValidationReport, validate_data

__all__ = ["DataLayout", "Issue", "ValidationReport", "validate_data"]
