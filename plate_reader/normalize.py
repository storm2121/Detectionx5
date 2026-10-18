"""Normalisation and lenient parsing of Moroccan licence-plate text.

Two civilian formats are recognised (their single definition is the automaton in
:mod:`plate_reader.grammar`):

* standard   ``24830-أ-1``  digits, one Arabic letter, then a region code
* temporary  ``72173 WW``   digits followed by the ``WW`` marker

OCR rarely returns either of those cleanly, so the text is repaired in stages before
the automaton judges it: strip decoration, fold the many Unicode spellings of each
Arabic letter onto one canonical form, then tokenise. Lookalike repair (``O`` read
for ``0``) is only ever effective where the automaton expects a digit, because each
lookalike is mapped to a digit symbol and digits are only accepted in digit fields.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

from .grammar import DIGITS, GRAMMAR, LETTERS, MARK, SEP, Plate, SymbolClass

# Kept for backwards compatibility; the definition lives in the grammar.
VALID_LETTERS: Final = LETTERS

_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_EXTENDED_ARABIC_DIGITS = "۰۱۲۳۴۵۶۷۸۹"

# Unicode spellings an OCR engine may return for each canonical letter.
_LETTER_VARIANTS: Final[dict[str, str]] = {
    "أ": "اإآٱٲٳﺍﺃٵ",
    "ب": "ٮپﺏﺑﺒﺐ",
    "د": "ذډڊﺩﺪ",
    "ه": "ةھہﻩﻪﻫﻬۀ",
    "و": "ؤۇۈۋﻭﻮ",
    "ط": "ظﻁﻄﻃﻂ",
}
if set(_LETTER_VARIANTS) != set(LETTERS):  # pragma: no cover - import-time guard
    raise RuntimeError("letter variants must cover exactly the grammar's letters")

# Applied only where a digit is expected, never across the whole string.
_LOOKALIKE_DIGITS: Final[dict[str, str]] = {
    "O": "0",
    "Q": "0",
    "D": "0",
    "I": "1",
    "L": "1",
    "|": "1",
    "!": "1",
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
        table[ord(char)] = SEP
    return table


_TRANSLATION: Final = _build_translation_table()


def normalize_text(raw: str) -> str:
    """Fold OCR output onto a canonical alphabet.

    Removes diacritics and control characters, unifies the many dash-like separators,
    converts Arabic-Indic digits to ASCII, and maps every Unicode spelling of the six
    plate letters onto its canonical form.
    """
    if not raw:
        return ""

    decomposed = unicodedata.normalize("NFKD", raw)
    stripped = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(char) and not unicodedata.category(char).startswith("C")
    )

    folded = stripped.translate(_TRANSLATION).upper()
    folded = re.sub(r"\s+", " ", folded)
    folded = re.sub(r"-{2,}", "-", folded)
    return folded.strip(" -")


@dataclass(frozen=True)
class _Token:
    symbol: str
    cls: SymbolClass
    soft: bool = False  # a separator made only of whitespace


def _tokenise(text: str) -> list[_Token] | None:
    """Map folded text onto grammar symbols, or ``None`` if any character is foreign."""
    tokens: list[_Token] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in (" ", SEP):
            end = index
            while end < len(text) and text[end] in (" ", SEP):
                end += 1
            tokens.append(_Token(SEP, SymbolClass.SEP, soft=SEP not in text[index:end]))
            index = end
            continue
        if char in DIGITS:
            tokens.append(_Token(char, SymbolClass.DIGIT))
        elif char in _LOOKALIKE_DIGITS:
            tokens.append(_Token(_LOOKALIKE_DIGITS[char], SymbolClass.DIGIT))
        elif char in LETTERS:
            tokens.append(_Token(char, SymbolClass.LETTER))
        elif char == MARK:
            tokens.append(_Token(char, SymbolClass.MARK))
        else:
            return None
        index += 1

    # OCR engines split one printed run into words: a whitespace-only gap between two
    # symbols of the same kind (digit-digit or W-W) is not a separator.
    merged: list[_Token] = []
    for position, token in enumerate(tokens):
        if (
            token.cls is SymbolClass.SEP
            and token.soft
            and 0 < position < len(tokens) - 1
            and tokens[position - 1].cls is tokens[position + 1].cls
            and tokens[position - 1].cls in (SymbolClass.DIGIT, SymbolClass.MARK)
        ):
            continue
        merged.append(token)
    return merged


def _needs_separator(previous: _Token | None, current: _Token) -> bool:
    """Separators are the first thing OCR loses: allow one at a digit/letter boundary."""
    if previous is None or SymbolClass.SEP in (previous.cls, current.cls):
        return False
    boundary = {previous.cls, current.cls}
    return SymbolClass.DIGIT in boundary and bool(boundary & {SymbolClass.LETTER, SymbolClass.MARK})


def parse_plate(raw: str) -> Plate | None:
    """Parse OCR output into a :class:`Plate`, or return ``None``.

    The text is normalised, tokenised onto grammar symbols and run through the
    automaton. A missing separator is tolerated (``24830أ1`` parses the same as
    ``24830-أ-1``) by letting the simulation insert one at a digit/letter boundary.
    """
    text = normalize_text(raw)
    if not text:
        return None
    tokens = _tokenise(text)
    if not tokens:
        return None

    # Simulate the DFA over every way of inserting the optional separators. The
    # language forces a separator before a letter, so at most one path survives.
    paths: dict[tuple[int, str], None] = {(GRAMMAR.start, ""): None}
    previous: _Token | None = None
    for token in tokens:
        advanced: dict[tuple[int, str], None] = {}
        for state, out in paths:
            target = GRAMMAR.step(state, token.symbol)
            if target >= 0:
                advanced[(target, out + token.symbol)] = None
            if _needs_separator(previous, token):
                via = GRAMMAR.step(GRAMMAR.step(state, SEP), token.symbol)
                if via >= 0:
                    advanced[(via, out + SEP + token.symbol)] = None
        paths = advanced
        previous = token
        if not paths:
            return None

    for state, out in paths:
        if GRAMMAR.is_accepting(state):
            return Plate.from_tokens(out)
    return None


def is_valid_plate(raw: str) -> bool:
    """Backwards-compatible boolean check."""
    return parse_plate(raw) is not None


__all__ = ["VALID_LETTERS", "Plate", "is_valid_plate", "normalize_text", "parse_plate"]
