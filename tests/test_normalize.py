"""Tests for plate text normalisation and parsing.

These run without the model or any OCR engine, so they are fast and are the
right place to pin down the repair rules.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plate_reader.normalize import is_valid_plate, normalize_text, parse_plate


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("24830-أ-1", "24830-أ-1"),
        ("24830 أ 1", "24830-أ-1"),          # separators lost by OCR
        ("24830أ1", "24830-أ-1"),            # no separators at all
        ("24830 ا 1", "24830-أ-1"),          # bare alif instead of hamza
        ("24830-آ-1", "24830-أ-1"),          # madda spelling
        ("٢٤٨٣٠-أ-١", "24830-أ-1"),          # Arabic-Indic digits
        ("24830-ة-1", "24830-ه-1"),          # ta marbuta folded onto ha
        ("24830-ظ-1", "24830-ط-1"),          # dha folded onto ta
        ("  24830 - أ - 1  ", "24830-أ-1"),  # stray whitespace
        ("2483O-أ-1", "24830-أ-1"),          # letter O read instead of zero
        ("2483O-أ-I", "24830-أ-1"),          # letter I read instead of one
    ],
)
def test_standard_plates(raw, expected):
    plate = parse_plate(raw)
    assert plate is not None, f"failed to parse {raw!r}"
    assert plate.text == expected
    assert not plate.is_temporary


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("72173 WW", "72173 WW"),
        ("72173WW", "72173 WW"),
        ("72173-WW", "72173 WW"),
        ("721735 ww", "721735 WW"),
    ],
)
def test_temporary_plates(raw, expected):
    plate = parse_plate(raw)
    assert plate is not None, f"failed to parse {raw!r}"
    assert plate.text == expected
    assert plate.is_temporary


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "hello world",
        "24830-ز-1",        # letter that never appears on a plate
        "248301234-أ-1",    # too many digits
        "24830-أ-123",      # region code too long
        "----",
        "WW",
    ],
)
def test_rejects_invalid(raw):
    assert parse_plate(raw) is None
    assert not is_valid_plate(raw)


def test_normalize_strips_control_characters():
    assert normalize_text("24830‏-أ-1\n") == "24830-أ-1"


def test_plate_components():
    plate = parse_plate("24830-أ-1")
    assert plate.digits == "24830"
    assert plate.letter == "أ"
    assert plate.region == "1"


def test_temporary_has_no_letter():
    plate = parse_plate("72173 WW")
    assert plate.letter is None
    assert plate.digits == "72173"
