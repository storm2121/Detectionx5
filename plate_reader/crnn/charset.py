"""The CRNN's output classes: the CTC blank followed by the grammar's symbols, in order.

The charset is derived from :data:`plate_reader.grammar.SYMBOLS` instead of being declared
here, so the recogniser, the constrained decoder and the browser port can never disagree
about which class means which symbol.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Final

from ..grammar import SYMBOL_INDEX, SYMBOLS

BLANK: Final = 0
CLASSES: Final[tuple[str, ...]] = ("<blank>", *SYMBOLS)
NUM_CLASSES: Final = len(CLASSES)
#: A short fingerprint of the class order, stored with every exported model.
CHARSET_ID: Final = hashlib.sha256("\0".join(CLASSES).encode()).hexdigest()[:12]


def encode(tokens: str) -> list[int]:
    """Class indices of a canonical token string (blank-free)."""
    return [SYMBOL_INDEX[symbol] + 1 for symbol in tokens]


def decode(indices: Iterable[int]) -> str:
    """Token string from class indices, skipping blanks (no repeat collapsing)."""
    return "".join(SYMBOLS[i - 1] for i in indices if i != BLANK)


__all__ = ["BLANK", "CHARSET_ID", "CLASSES", "NUM_CLASSES", "decode", "encode"]
