"""Normalisation and validation of Moroccan licence-plate text.

Two civilian formats are recognised:

* standard   ``24830-أ-1``  digits, one Arabic letter, then a region code
* temporary  ``72173 WW``   digits followed by the ``WW`` marker

OCR rarely returns either of those cleanly, so the text is repaired in
stages before it is parsed: strip decoration, fold the many Unicode spellings
of each Arabic letter onto one canonical form, then — only inside groups that
are meant to be numeric — undo the usual letter/digit lookalike mistakes.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# The six letters that have actually appeared on Moroccan civilian plates.
VALID_LETTERS = "أبدهوط"

_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_EXTENDED_ARABIC_DIGITS = "۰۱۲۳۴۵۶۷۸۹"

# Unicode spellings an OCR engine may return for each canonical letter.
_LETTER_VARIANTS = {
    "أ": "اإآٱٲٳﺍﺃٵ",
    "ب": "ٮپﺏﺑﺒﺐ",
    "د": "ذډڊﺩﺪ",
    "ه": "ةھہﻩﻪﻫﻬۀ",
    "و": "ؤۇۈۋﻭﻮ",
    "ط": "ظﻁﻄﻃﻂ",
}

# Applied only where a digit is expected, never across the whole string.
_LOOKALIKE_DIGITS = {
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1", "|": "1", "!": "1",
    "Z": "2",
    "E": "3",
    "A": "4",
    "S": "5",
    "G": "6",
    "T": "7",
    "B": "8",
    "P": "9",
}

_SEPARATORS = "–—−‒―ـ_/\\.·•"

# The digit groups must not swallow a separator, so dashes and whitespace are
# excluded from them rather than relying on backtracking to sort it out.
_STANDARD_RE = re.compile(
    rf"^([^-\s]{{1,5}})-([{VALID_LETTERS}])-([^-\s]{{1,2}})$"
)
_TEMPORARY_RE = re.compile(r"^([^-\s]{5,6})[-\s]?WW$")


def _build_translation_table() -> dict[int, str]:
    table: dict[int, str] = {}
    for index, char in enumerate(_ARABIC_INDIC_DIGITS):
        table[ord(char)] = str(index)
    for index, char in enumerate(_EXTENDED_ARABIC_DIGITS):
        table[ord(char)] = str(index)
    for canonical, variants in _LETTER_VARIANTS.items():
        for char in variants:
            table[ord(char)] = canonical
    for char in _SEPARATORS:
        table[ord(char)] = "-"
    return table


_TRANSLATION = _build_translation_table()


@dataclass(frozen=True)
class Plate:
    """A successfully parsed plate."""

    digits: str
    letter: str | None = None
    region: str | None = None

    @property
    def is_temporary(self) -> bool:
        return self.letter is None

    @property
    def text(self) -> str:
        if self.is_temporary:
            return f"{self.digits} WW"
        return f"{self.digits}-{self.letter}-{self.region}"

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.text


def normalize_text(raw: str) -> str:
    """Fold OCR output onto a canonical alphabet.

    Removes diacritics and control characters, unifies the many dash-like
    separators, converts Arabic-Indic digits to ASCII, and maps every Unicode
    spelling of the six plate letters onto its canonical form.
    """
    if not raw:
        return ""

    decomposed = unicodedata.normalize("NFKD", raw)
    stripped = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(char)
        and not unicodedata.category(char).startswith("C")
    )

    folded = stripped.translate(_TRANSLATION).upper()
    folded = re.sub(r"\s+", " ", folded)
    folded = re.sub(r"-{2,}", "-", folded)
    return folded.strip(" -")


def _repair_digits(group: str) -> str | None:
    """Coerce a group that should be numeric into digits, or give up."""
    repaired = "".join(_LOOKALIKE_DIGITS.get(char, char) for char in group)
    return repaired if repaired.isdigit() else None


def parse_plate(raw: str) -> Plate | None:
    """Parse OCR output into a :class:`Plate`, or return ``None``.

    The text is normalised first, then matched against both plate formats.
    A missing separator is tolerated — ``24830أ1`` parses the same as
    ``24830-أ-1`` — because separators are the first thing OCR loses.
    """
    text = normalize_text(raw)
    if not text:
        return None

    # Insert the separators OCR dropped, so one regex handles both spellings,
    # then tighten up whitespace left sitting next to a separator.
    spaced = re.sub(rf"\s*([{VALID_LETTERS}])\s*", r"-\1-", text)
    spaced = re.sub(r"-{2,}", "-", spaced)
    spaced = re.sub(r"\s*-\s*", "-", spaced).strip(" -")

    match = _STANDARD_RE.match(spaced)
    if match:
        digits = _repair_digits(match.group(1))
        region = _repair_digits(match.group(3))
        if digits and region:
            return Plate(digits=digits, letter=match.group(2), region=region)
        return None

    match = _TEMPORARY_RE.match(text.replace(" ", ""))
    if match:
        digits = _repair_digits(match.group(1))
        if digits:
            return Plate(digits=digits)

    return None


def is_valid_plate(raw: str) -> bool:
    """Backwards-compatible boolean check."""
    return parse_plate(raw) is not None
