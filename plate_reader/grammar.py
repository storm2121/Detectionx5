"""The Moroccan plate language, defined once as an explicit finite automaton.

Why an automaton and not regular expressions: the same definition has to validate
strings, prune a CTC beam search one token at a time, filter fusion candidates, drive
the synthetic generator and produce near-misses for the tests. A regex only answers
"does the whole string match"; a DFA also answers "which symbols may follow this
prefix" and "can this prefix still become a plate", which is what decoding needs.

Formats are declared as sequences of fields (a symbol class and a length range). They
are compiled into an NFA whose states remember (format, field, count), determinised by
subset construction and minimised by partition refinement. Adding a format means adding
one :class:`PlateFormat`; every consumer picks it up.

Two spellings exist for every plate:

* the canonical *token* string uses one separator symbol, ``-``, for both formats
  (``24830-ب-1``, ``72173-WW``). Models, decoders and the automaton work on tokens,
  because the recogniser has a single separator class.
* the *display* string is what people read (``24830-ب-1``, ``72173 WW``), produced by
  :attr:`Plate.text`.
"""

from __future__ import annotations

import enum
from collections import deque
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Final, Protocol, SupportsInt, runtime_checkable

DIGITS: Final = "0123456789"
# The six letters that have actually appeared on Moroccan civilian plates.
LETTERS: Final = "أبدهوط"
MARK: Final = "W"
SEP: Final = "-"

#: Every symbol of the canonical alphabet, in a fixed order. The CRNN charset is this
#: tuple with the CTC blank prepended, so the order is part of the model contract.
SYMBOLS: Final[tuple[str, ...]] = (*DIGITS, *LETTERS, MARK, SEP)
SYMBOL_INDEX: Final[Mapping[str, int]] = {symbol: i for i, symbol in enumerate(SYMBOLS)}

#: The implicit rejecting sink state.
DEAD: Final = -1


class SymbolClass(enum.Enum):
    """The kinds of symbol a plate field can hold."""

    DIGIT = "digit"
    LETTER = "letter"
    MARK = "mark"
    SEP = "sep"

    @property
    def members(self) -> str:
        return _CLASS_MEMBERS[self]


_CLASS_MEMBERS: Final[Mapping[SymbolClass, str]] = {
    SymbolClass.DIGIT: DIGITS,
    SymbolClass.LETTER: LETTERS,
    SymbolClass.MARK: MARK,
    SymbolClass.SEP: SEP,
}


def symbol_class(symbol: str) -> SymbolClass:
    """Return the class of one canonical symbol; raises ``KeyError`` for anything else."""
    if len(symbol) == 1:
        for cls, members in _CLASS_MEMBERS.items():
            if symbol in members:
                return cls
    raise KeyError(symbol)


@dataclass(frozen=True)
class Field:
    """One printed field: a symbol class repeated between ``min_len`` and ``max_len`` times."""

    name: str
    symbol_class: SymbolClass
    min_len: int
    max_len: int

    def __post_init__(self) -> None:
        if not 0 <= self.min_len <= self.max_len or self.max_len == 0:
            raise ValueError(f"invalid length range for field {self.name!r}")

    @property
    def is_constant(self) -> bool:
        """A field with one possible content (the ``WW`` mark) carries no information."""
        return len(self.symbol_class.members) == 1 and self.min_len == self.max_len

    @property
    def is_separator(self) -> bool:
        return self.symbol_class is SymbolClass.SEP


@dataclass(frozen=True)
class PlateFormat:
    """A plate format as an ordered sequence of fields."""

    name: str
    fields: tuple[Field, ...]
    display_separator: str

    def field(self, name: str) -> Field:
        for item in self.fields:
            if item.name == name:
                return item
        raise KeyError(name)

    @property
    def min_length(self) -> int:
        return sum(f.min_len for f in self.fields)

    @property
    def max_length(self) -> int:
        return sum(f.max_len for f in self.fields)


STANDARD: Final = PlateFormat(
    name="standard",
    fields=(
        Field("digits", SymbolClass.DIGIT, 1, 5),
        Field("sep1", SymbolClass.SEP, 1, 1),
        Field("letter", SymbolClass.LETTER, 1, 1),
        Field("sep2", SymbolClass.SEP, 1, 1),
        Field("region", SymbolClass.DIGIT, 1, 2),
    ),
    display_separator="-",
)

TEMPORARY: Final = PlateFormat(
    name="temporary",
    fields=(
        Field("digits", SymbolClass.DIGIT, 1, 6),
        Field("sep", SymbolClass.SEP, 1, 1),
        Field("mark", SymbolClass.MARK, 2, 2),
    ),
    display_separator=" ",
)

FORMATS: Final[tuple[PlateFormat, ...]] = (STANDARD, TEMPORARY)
FORMAT_NAMES: Final[tuple[str, ...]] = tuple(f.name for f in FORMATS)

_NfaState = tuple[int, int, int]  # (format index, field index, symbols consumed in field)


@runtime_checkable
class _NumpyLikeRng(Protocol):
    def integers(self, low: int, high: int) -> SupportsInt: ...


@runtime_checkable
class _StdlibLikeRng(Protocol):
    def randrange(self, start: int, stop: int) -> int: ...


def _randint(rng: object, low: int, high: int) -> int:
    """Uniform integer in ``[low, high)`` from a numpy Generator or a ``random.Random``."""
    if isinstance(rng, _NumpyLikeRng):
        return int(rng.integers(low, high))
    if isinstance(rng, _StdlibLikeRng):
        return rng.randrange(low, high)
    raise TypeError("rng must be a numpy Generator or a random.Random")


class PlateGrammar:
    """A minimal DFA over :data:`SYMBOLS` compiled from a tuple of formats.

    States are small integers; ``DEAD`` (-1) is the implicit rejecting sink. The
    transition table is a list of lists indexed by ``[state][symbol index]`` so that
    decoders can step without hashing strings. Every live state is a viable prefix:
    states that cannot reach acceptance are removed at compile time.
    """

    def __init__(
        self,
        formats: Sequence[PlateFormat],
        transitions: list[list[int]],
        accepting: list[frozenset[str]],
        possible: list[frozenset[str]],
    ) -> None:
        self.formats: tuple[PlateFormat, ...] = tuple(formats)
        self._delta = transitions
        self._accepting = accepting
        self._possible = possible
        self.start = 0

    # --- construction ------------------------------------------------------
    @classmethod
    def compile(cls, formats: Sequence[PlateFormat]) -> PlateGrammar:
        if not formats:
            raise ValueError("at least one format is required")
        names = [f.name for f in formats]
        if len(set(names)) != len(names):
            raise ValueError("format names must be unique")

        def closure(states: Iterable[_NfaState]) -> frozenset[_NfaState]:
            stack = list(states)
            seen = set(stack)
            while stack:
                f, i, c = stack.pop()
                fields = formats[f].fields
                if i < len(fields) and c >= fields[i].min_len:
                    nxt = (f, i + 1, 0)
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            return frozenset(seen)

        def move(states: frozenset[_NfaState], symbol: str) -> frozenset[_NfaState]:
            out: set[_NfaState] = set()
            for f, i, c in states:
                fields = formats[f].fields
                if (
                    i < len(fields)
                    and c < fields[i].max_len
                    and symbol in fields[i].symbol_class.members
                ):
                    out.add((f, i, c + 1))
            return closure(out)

        start = closure((f, 0, 0) for f in range(len(formats)))
        ids: dict[frozenset[_NfaState], int] = {start: 0}
        order: list[frozenset[_NfaState]] = [start]
        delta: list[list[int]] = []
        queue: deque[frozenset[_NfaState]] = deque([start])
        while queue:
            current = queue.popleft()
            row: list[int] = []
            for symbol in SYMBOLS:
                target = move(current, symbol)
                if not target:
                    row.append(DEAD)
                    continue
                if target not in ids:
                    ids[target] = len(order)
                    order.append(target)
                    queue.append(target)
                row.append(ids[target])
            delta.append(row)

        accepting = [
            frozenset(formats[f].name for f, i, _ in s if i == len(formats[f].fields))
            for s in order
        ]
        possible = [frozenset(formats[f].name for f, _, _ in s) for s in order]
        delta, accepting, possible = _minimise(delta, accepting, possible)
        return cls(formats, delta, accepting, possible)

    # --- stepping ----------------------------------------------------------
    @property
    def num_states(self) -> int:
        return len(self._delta)

    def step_index(self, state: int, symbol_index: int) -> int:
        """Transition by symbol index; returns ``DEAD`` when the move is impossible."""
        if state == DEAD:
            return DEAD
        return self._delta[state][symbol_index]

    def step(self, state: int, symbol: str) -> int:
        index = SYMBOL_INDEX.get(symbol)
        if index is None:
            return DEAD
        return self.step_index(state, index)

    def run(self, tokens: str, state: int | None = None) -> int:
        """State reached after consuming ``tokens`` (``DEAD`` once a move fails)."""
        current = self.start if state is None else state
        for symbol in tokens:
            current = self.step(current, symbol)
            if current == DEAD:
                return DEAD
        return current

    def as_dict(self) -> dict[str, Any]:
        """The automaton as plain data, for the browser runtime (``plate export web``)."""
        return {
            "schema": "detectionx5.grammar/1",
            "symbols": list(SYMBOLS),
            "start": self.start,
            "dead": DEAD,
            "transitions": [list(row) for row in self._delta],
            "accepting": [sorted(names) for names in self._accepting],
        }

    def is_accepting(self, state: int) -> bool:
        return state != DEAD and bool(self._accepting[state])

    def accepting_formats(self, state: int) -> frozenset[str]:
        return frozenset() if state == DEAD else self._accepting[state]

    def possible_formats(self, state: int) -> frozenset[str]:
        """Formats still reachable from ``state``; used to label partial reads."""
        return frozenset() if state == DEAD else self._possible[state]

    def allowed_indices(self, state: int) -> tuple[int, ...]:
        if state == DEAD:
            return ()
        return tuple(i for i, target in enumerate(self._delta[state]) if target != DEAD)

    def allowed(self, state: int) -> frozenset[str]:
        """Symbols that keep the prefix completable; this is what prunes the beam."""
        return frozenset(SYMBOLS[i] for i in self.allowed_indices(state))

    # --- language queries --------------------------------------------------
    def accepts(self, tokens: str) -> bool:
        return self.is_accepting(self.run(tokens))

    def is_viable_prefix(self, tokens: str) -> bool:
        """True when ``tokens`` can still be extended into an accepted string."""
        return self.run(tokens) != DEAD

    def format_of(self, tokens: str) -> str | None:
        formats = self.accepting_formats(self.run(tokens))
        return min(formats) if formats else None

    @cached_property
    def _completion_counts(self) -> list[int]:
        # The language is finite, so the DFA is acyclic and a memoised DFS terminates.
        memo: dict[int, int] = {}

        def count(state: int) -> int:
            if state in memo:
                return memo[state]
            total = 1 if self._accepting[state] else 0
            for target in self._delta[state]:
                if target != DEAD:
                    total += count(target)
            memo[state] = total
            return total

        return [count(s) for s in range(self.num_states)]

    def count_completions(self, state: int | None = None) -> int:
        """Number of accepted strings reachable from ``state`` (the language size at start)."""
        current = self.start if state is None else state
        return 0 if current == DEAD else self._completion_counts[current]

    def enumerate_completions(self, prefix: str = "", limit: int | None = None) -> Iterator[str]:
        """Accepted strings extending ``prefix``, shortest first, then in symbol order."""
        state = self.run(prefix)
        if state == DEAD:
            return
        produced = 0
        frontier: deque[tuple[int, str]] = deque([(state, prefix)])
        while frontier:
            current, text = frontier.popleft()
            if self._accepting[current]:
                yield text
                produced += 1
                if limit is not None and produced >= limit:
                    return
            for index, target in enumerate(self._delta[current]):
                if target != DEAD:
                    frontier.append((target, text + SYMBOLS[index]))

    def segment(self, tokens: str) -> tuple[PlateFormat, dict[str, str]] | None:
        """Split an accepted token string into its named fields."""
        for fmt in self.formats:
            parts = _split_fields(fmt.fields, tokens)
            if parts is not None:
                return fmt, parts
        return None

    def random_tokens(self, rng: object, fmt: str | PlateFormat | None = None) -> str:
        """Sample a plate: format uniform, each field length uniform, symbols uniform.

        Numeric fields never start with zero because real serials and region codes do
        not; the grammar itself accepts leading zeros so that OCR output is not
        rejected for them.
        """
        if fmt is None:
            chosen = self.formats[_randint(rng, 0, len(self.formats))]
        elif isinstance(fmt, PlateFormat):
            chosen = fmt
        else:
            matches = [f for f in self.formats if f.name == fmt]
            if not matches:
                raise KeyError(fmt)
            chosen = matches[0]
        out: list[str] = []
        for item in chosen.fields:
            length = _randint(rng, item.min_len, item.max_len + 1)
            members = item.symbol_class.members
            for position in range(length):
                pool = members
                if item.symbol_class is SymbolClass.DIGIT and position == 0:
                    pool = members[1:]
                out.append(pool[_randint(rng, 0, len(pool))])
        return "".join(out)


def _split_fields(fields: Sequence[Field], tokens: str) -> dict[str, str] | None:
    """Backtracking split of ``tokens`` into ``fields``; inputs are a dozen symbols at most."""
    if not fields:
        return {} if not tokens else None
    head, rest = fields[0], fields[1:]
    for length in range(head.max_len, head.min_len - 1, -1):
        chunk = tokens[:length]
        if len(chunk) != length or any(s not in head.symbol_class.members for s in chunk):
            continue
        tail = _split_fields(rest, tokens[length:])
        if tail is not None:
            return {head.name: chunk, **tail}
    return None


def _minimise(
    delta: list[list[int]],
    accepting: list[frozenset[str]],
    possible: list[frozenset[str]],
) -> tuple[list[list[int]], list[frozenset[str]], list[frozenset[str]]]:
    """Moore partition refinement, then breadth-first renumbering from the start state.

    States that cannot reach acceptance are dropped first, so that every live state is
    a viable prefix: the invariant constrained decoding relies on.
    """
    n = len(delta)
    reverse: list[set[int]] = [set() for _ in range(n)]
    for source, row in enumerate(delta):
        for target in row:
            if target != DEAD:
                reverse[target].add(source)
    live = {s for s in range(n) if accepting[s]}
    stack = list(live)
    while stack:
        for source in reverse[stack.pop()]:
            if source not in live:
                live.add(source)
                stack.append(source)
    if 0 not in live:
        raise ValueError("the grammar accepts nothing")

    pruned = [[t if t in live else DEAD for t in row] for row in delta]
    states = sorted(live)
    # Initial partition: states with the same accepted and possible formats.
    signature: dict[int, object] = {s: (accepting[s], possible[s]) for s in states}
    while True:
        keys = sorted({repr(v) for v in signature.values()})
        index = {k: i for i, k in enumerate(keys)}
        labelled = {s: index[repr(signature[s])] for s in states}
        refined: dict[int, object] = {
            s: (labelled[s], tuple(labelled[t] if t != DEAD else DEAD for t in pruned[s]))
            for s in states
        }
        if len({repr(v) for v in refined.values()}) == len(keys):
            break
        signature = refined

    representative: dict[int, int] = {}
    for s in states:
        representative.setdefault(labelled[s], s)
    new_id: dict[int, int] = {labelled[0]: 0}
    queue: deque[int] = deque([labelled[0]])
    while queue:
        block = queue.popleft()
        for target in pruned[representative[block]]:
            if target != DEAD and labelled[target] not in new_id:
                new_id[labelled[target]] = len(new_id)
                queue.append(labelled[target])
    size = len(new_id)
    out_delta = [[DEAD] * len(SYMBOLS) for _ in range(size)]
    out_accepting: list[frozenset[str]] = [frozenset()] * size
    out_possible: list[frozenset[str]] = [frozenset()] * size
    for block, new in new_id.items():
        rep = representative[block]
        out_accepting[new] = accepting[rep]
        out_possible[new] = possible[rep]
        out_delta[new] = [new_id[labelled[t]] if t != DEAD else DEAD for t in pruned[rep]]
    return out_delta, out_accepting, out_possible


#: The compiled grammar every module uses.
GRAMMAR: Final = PlateGrammar.compile(FORMATS)


@dataclass(frozen=True)
class Plate:
    """A grammar-valid plate split into its fields; temporary plates have no letter."""

    digits: str
    letter: str | None = None
    region: str | None = None

    def __post_init__(self) -> None:
        if not GRAMMAR.accepts(self.tokens):
            raise ValueError(f"not a valid plate: {self.digits!r} {self.letter!r} {self.region!r}")

    @property
    def is_temporary(self) -> bool:
        return self.letter is None

    @property
    def format(self) -> str:
        return TEMPORARY.name if self.is_temporary else STANDARD.name

    @property
    def tokens(self) -> str:
        """Canonical token string: the form models and decoders use."""
        if self.is_temporary:
            return f"{self.digits}{SEP}{MARK * 2}"
        return f"{self.digits}{SEP}{self.letter}{SEP}{self.region or ''}"

    @property
    def text(self) -> str:
        """Display string: the form people read and the API returns."""
        return to_display(self.tokens)

    @classmethod
    def from_tokens(cls, tokens: str) -> Plate | None:
        split = GRAMMAR.segment(tokens)
        if split is None:
            return None
        _, parts = split
        return cls(digits=parts["digits"], letter=parts.get("letter"), region=parts.get("region"))

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.text


def to_display(tokens: str) -> str:
    """Map a canonical token string to its display spelling (``72173-WW`` to ``72173 WW``)."""
    split = GRAMMAR.segment(tokens)
    if split is None:
        raise ValueError(f"not a valid plate token string: {tokens!r}")
    fmt, _ = split
    return tokens.replace(SEP, fmt.display_separator)


# --- module-level convenience API ------------------------------------------------
def accepts(tokens: str) -> bool:
    """Strict acceptance of a canonical token string."""
    return GRAMMAR.accepts(tokens)


def transition(state: int, symbol: str) -> int:
    return GRAMMAR.step(state, symbol)


def enumerate_completions(prefix: str = "", limit: int | None = None) -> Iterator[str]:
    return GRAMMAR.enumerate_completions(prefix, limit)


def random_plate(rng: object, fmt: str | PlateFormat | None = None) -> str:
    """A random canonical token string (see :meth:`PlateGrammar.random_tokens`)."""
    return GRAMMAR.random_tokens(rng, fmt)


def parse(raw: str) -> Plate | None:
    """Lenient parse of raw OCR text into a :class:`Plate` (rules in :mod:`.normalize`)."""
    # normalize.py builds its character folding on this module's alphabet, so the
    # import is deferred to call time to keep the module dependency one-directional.
    from .normalize import parse_plate

    return parse_plate(raw)


def normalize(raw: str) -> str | None:
    """Raw text to the display spelling of the plate it denotes, or ``None``.

    Idempotent: ``normalize(normalize(s)) == normalize(s)`` whenever the first call
    succeeds, which the property tests assert.
    """
    plate = parse(raw)
    return plate.text if plate is not None else None


__all__ = [
    "DEAD",
    "DIGITS",
    "FORMATS",
    "FORMAT_NAMES",
    "GRAMMAR",
    "LETTERS",
    "MARK",
    "SEP",
    "STANDARD",
    "SYMBOLS",
    "SYMBOL_INDEX",
    "TEMPORARY",
    "Field",
    "Plate",
    "PlateFormat",
    "PlateGrammar",
    "SymbolClass",
    "accepts",
    "enumerate_completions",
    "normalize",
    "parse",
    "random_plate",
    "symbol_class",
    "to_display",
    "transition",
]
