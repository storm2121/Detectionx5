"""Edit distance and alignment on plate strings.

Shared by the evaluation harness (character error rate) and by fusion (per-position
character posteriors come from aligning every hypothesis to the winner). Plate strings are
at most a dozen symbols, so the quadratic dynamic programme is the right tool.
"""

from __future__ import annotations

from collections.abc import Sequence

from .grammar import SEP

#: One alignment column: (index in a, index in b); ``None`` marks a gap.
Column = tuple[int | None, int | None]


def glyphs(tokens: str) -> str:
    """The printed characters of a token string, without separators."""
    return tokens.replace(SEP, "")


def _table(a: Sequence[str], b: Sequence[str]) -> list[list[int]]:
    rows, cols = len(a) + 1, len(b) + 1
    table = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        table[i][0] = i
    for j in range(cols):
        table[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            table[i][j] = min(table[i - 1][j] + 1, table[i][j - 1] + 1, table[i - 1][j - 1] + cost)
    return table


def levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    return _table(a, b)[len(a)][len(b)]


def align(a: Sequence[str], b: Sequence[str]) -> list[Column]:
    """A minimum-cost alignment; ties prefer substitution, then deletion, then insertion.

    The fixed tie order makes the alignment a function of its inputs, which keeps fusion
    deterministic and permutation-invariant.
    """
    table = _table(a, b)
    i, j = len(a), len(b)
    columns: list[Column] = []
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            cost = 0 if a[i - 1] == b[j - 1] else 1
            if table[i][j] == table[i - 1][j - 1] + cost:
                columns.append((i - 1, j - 1))
                i, j = i - 1, j - 1
                continue
        if i > 0 and table[i][j] == table[i - 1][j] + 1:
            columns.append((i - 1, None))
            i -= 1
        else:
            columns.append((None, j - 1))
            j -= 1
    columns.reverse()
    return columns


__all__ = ["Column", "align", "glyphs", "levenshtein"]
