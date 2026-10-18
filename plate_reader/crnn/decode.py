"""CTC decoding in numpy: greedy, prefix beam search, grammar-constrained prefix beam search.

Decoding runs outside the network so PyTorch, ONNX Runtime and the browser share one
definition (ADR 0003). The constrained search carries the automaton state of every prefix
and only extends a prefix with symbols the automaton allows; because every live automaton
state is a viable prefix, pruning never discards a prefix that could still become a plate,
and at the last frame only accepting prefixes are kept. Probabilities are log-space sums
over alignments (blank-ending and symbol-ending mass per prefix), the standard CTC
prefix-beam recursion.

Temperature ``T`` divides the logits before the softmax; ``T > 1`` flattens and ``T < 1``
sharpens the per-frame distributions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

from ..grammar import DEAD, GRAMMAR, PlateGrammar
from ..hypotheses import Hypothesis
from .charset import BLANK, decode, encode

FloatArray = npt.NDArray[np.float64]
NEG_INF: Final = -math.inf
DEFAULT_BEAM: Final = 10
#: Symbols whose frame log-probability is below this are not used to extend prefixes.
DEFAULT_PRUNE: Final = -14.0


def log_softmax(logits: npt.ArrayLike, temperature: float = 1.0) -> FloatArray:
    """Row-wise log-softmax of ``logits / temperature`` (``(T, C)`` or ``(B, T, C)``)."""
    x = np.asarray(logits, dtype=np.float64) / float(temperature)
    x = x - x.max(axis=-1, keepdims=True)
    return x - np.log(np.exp(x).sum(axis=-1, keepdims=True))


def _logaddexp(a: float, b: float) -> float:
    if a == NEG_INF:
        return b
    if b == NEG_INF:
        return a
    if a > b:
        return a + math.log1p(math.exp(b - a))
    return b + math.log1p(math.exp(a - b))


def greedy(log_probs: FloatArray) -> tuple[str, float]:
    """Best path: argmax per frame, collapse repeats, drop blanks; score is the path log-prob."""
    best = log_probs.argmax(axis=-1)
    score = float(log_probs[np.arange(len(best)), best].sum())
    collapsed: list[int] = []
    previous = BLANK
    for index in best.tolist():
        if index != previous and index != BLANK:
            collapsed.append(index)
        previous = index
    return decode(collapsed), score


@dataclass
class _Beam:
    blank: float = NEG_INF  # log-prob of alignments ending in blank
    symbol: float = NEG_INF  # log-prob of alignments ending in the last symbol
    state: int = 0

    @property
    def total(self) -> float:
        return _logaddexp(self.blank, self.symbol)


def _slot(table: dict[tuple[int, ...], _Beam], prefix: tuple[int, ...], state: int) -> _Beam:
    beam = table.get(prefix)
    if beam is None:
        beam = table[prefix] = _Beam(state=state)
    return beam


def prefix_beam_search(
    log_probs: FloatArray,
    beam_width: int = DEFAULT_BEAM,
    grammar: PlateGrammar | None = None,
    prune: float = DEFAULT_PRUNE,
) -> tuple[Hypothesis, ...]:
    """Top prefixes with their summed alignment log-probabilities, best first.

    With ``grammar`` the search is constrained: a prefix is extended only by symbols the
    automaton allows from its state, and only accepting prefixes are returned.
    """
    start = grammar.start if grammar is not None else 0
    beams: dict[tuple[int, ...], _Beam] = {(): _Beam(blank=0.0, symbol=NEG_INF, state=start)}
    frames, classes = log_probs.shape
    for t in range(frames):
        row = log_probs[t]
        candidates = [c for c in range(1, classes) if row[c] > prune]
        nxt: dict[tuple[int, ...], _Beam] = {}
        for prefix, beam in beams.items():
            total = beam.total
            # Blank: the prefix is unchanged and now ends in blank.
            stay = _slot(nxt, prefix, beam.state)
            stay.blank = _logaddexp(stay.blank, total + float(row[BLANK]))
            last = prefix[-1] if prefix else None
            if last is not None:
                # Repeating the last symbol without a blank collapses onto the same prefix.
                stay.symbol = _logaddexp(stay.symbol, beam.symbol + float(row[last]))
            for c in candidates:
                state = beam.state
                if grammar is not None:
                    state = grammar.step_index(beam.state, c - 1)
                    if state == DEAD:
                        continue
                extended = _slot(nxt, (*prefix, c), state)
                # A repeated symbol needs a blank in between to count twice.
                source = beam.blank if c == last else total
                extended.symbol = _logaddexp(extended.symbol, source + float(row[c]))
        ranked = sorted(nxt.items(), key=lambda kv: kv[1].total, reverse=True)
        beams = dict(ranked[:beam_width])

    results = []
    for prefix, beam in beams.items():
        if not prefix:
            continue
        if grammar is not None and not grammar.is_accepting(beam.state):
            continue
        results.append(Hypothesis(decode(prefix), beam.total))
    results.sort(key=lambda h: (-h.logp, h.tokens))
    return tuple(results)


def constrained_beam_search(
    log_probs: FloatArray, beam_width: int = DEFAULT_BEAM, prune: float = DEFAULT_PRUNE
) -> tuple[Hypothesis, ...]:
    return prefix_beam_search(log_probs, beam_width, GRAMMAR, prune)


def ctc_log_likelihood(log_probs: FloatArray, tokens: str) -> float:
    """Exact ``log p(tokens | x)`` by the CTC forward algorithm (used to check the beam)."""
    target = encode(tokens)
    extended = [BLANK]
    for symbol in target:
        extended += [symbol, BLANK]
    states = len(extended)
    alpha = np.full(states, NEG_INF)
    alpha[0] = log_probs[0, BLANK]
    if states > 1:
        alpha[1] = log_probs[0, extended[1]]
    for t in range(1, log_probs.shape[0]):
        previous = alpha.copy()
        for s in range(states):
            total = previous[s]
            if s >= 1:
                total = _logaddexp(total, previous[s - 1])
            if s >= 2 and extended[s] != BLANK and extended[s] != extended[s - 2]:
                total = _logaddexp(total, previous[s - 2])
            alpha[s] = total + log_probs[t, extended[s]] if total != NEG_INF else NEG_INF
    if states == 1:
        return float(alpha[0])
    return _logaddexp(float(alpha[-1]), float(alpha[-2]))


__all__ = [
    "DEFAULT_BEAM",
    "DEFAULT_PRUNE",
    "constrained_beam_search",
    "ctc_log_likelihood",
    "greedy",
    "log_softmax",
    "prefix_beam_search",
]
