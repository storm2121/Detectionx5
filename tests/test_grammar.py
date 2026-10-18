"""Property tests for the plate automaton, the single definition of plate formats."""

from __future__ import annotations

import random
import re

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from plate_reader import grammar
from plate_reader.grammar import (
    DEAD,
    DIGITS,
    FORMATS,
    GRAMMAR,
    LETTERS,
    MARK,
    SEP,
    STANDARD,
    SYMBOLS,
    TEMPORARY,
    Field,
    Plate,
    PlateFormat,
    PlateGrammar,
    SymbolClass,
)
from plate_reader.normalize import _LETTER_VARIANTS, parse_plate

# Arabic letters that never appear on Moroccan civilian plates (none of them is a variant
# that normalisation folds onto one of the six).
NON_PLATE_LETTERS = "جحخرزسشصضعغفقكلمني"


def oracle_regex(formats: tuple[PlateFormat, ...]) -> re.Pattern[str]:
    """An independent compilation of the same specification, built in the test."""
    alternatives = []
    for fmt in formats:
        parts = [
            f"[{re.escape(f.symbol_class.members)}]{{{f.min_len},{f.max_len}}}" for f in fmt.fields
        ]
        alternatives.append("".join(parts))
    return re.compile("|".join(f"(?:{a})" for a in alternatives))


ORACLE = oracle_regex(FORMATS)

plates = st.randoms(use_true_random=False).map(grammar.random_plate)
symbol_strings = st.text(alphabet=st.sampled_from(SYMBOLS), max_size=14)


@st.composite
def mutated_plates(draw: st.DrawFn) -> str:
    """Valid plates with one random edit: dense coverage of the language's boundary."""
    tokens = list(draw(plates))
    op = draw(st.sampled_from(["insert", "delete", "replace", "swap"]))
    position = draw(st.integers(0, max(0, len(tokens) - 1)))
    symbol = draw(st.sampled_from(SYMBOLS))
    if op == "insert":
        tokens.insert(position, symbol)
    elif op == "delete" and tokens:
        del tokens[position]
    elif op == "replace" and tokens:
        tokens[position] = symbol
    elif op == "swap" and len(tokens) > 1:
        other = draw(st.integers(0, len(tokens) - 1))
        tokens[position], tokens[other] = tokens[other], tokens[position]
    return "".join(tokens)


# --- acceptance -----------------------------------------------------------------
@given(plates)
def test_random_plates_are_accepted(tokens: str) -> None:
    assert grammar.accepts(tokens)
    plate = Plate.from_tokens(tokens)
    assert plate is not None
    assert plate.tokens == tokens


@given(st.one_of(symbol_strings, mutated_plates()))
def test_automaton_agrees_with_an_independent_compilation(tokens: str) -> None:
    assert GRAMMAR.accepts(tokens) == bool(ORACLE.fullmatch(tokens))


@given(plates)
def test_display_round_trips_through_lenient_parsing(tokens: str) -> None:
    plate = Plate.from_tokens(tokens)
    assert plate is not None
    parsed = parse_plate(plate.text)
    assert parsed == plate
    assert grammar.normalize(plate.text) == plate.text


@given(plates)
def test_every_prefix_is_viable_and_allowed_symbols_lead_somewhere(tokens: str) -> None:
    state = GRAMMAR.start
    for symbol in tokens:
        assert symbol in GRAMMAR.allowed(state)
        state = GRAMMAR.step(state, symbol)
        assert state != DEAD
    assert GRAMMAR.is_accepting(state)
    for symbol in GRAMMAR.allowed(state):
        assert GRAMMAR.count_completions(GRAMMAR.step(state, symbol)) > 0


# --- near-misses ------------------------------------------------------------------
@given(plates.filter(lambda t: Plate.from_tokens(t).format == "standard"), st.data())  # type: ignore[union-attr]
def test_near_misses_are_rejected(tokens: str, data: st.DataObject) -> None:
    digits, letter, region = tokens.split(SEP)
    foreign = data.draw(st.sampled_from(NON_PLATE_LETTERS))
    position = data.draw(st.integers(0, len(digits) - 1))
    near_misses = [
        f"{digits}{SEP}{foreign}{SEP}{region}",  # a seventh letter
        f"{digits}{letter}{SEP}{region}",  # missing separator
        f"{digits}{SEP}{letter}{region}",  # missing separator
        f"{digits}{letter}{region}",  # no separators at all
        digits[:position] + letter + digits[position + 1 :] + f"{SEP}{letter}{SEP}{region}",
        f"{digits}{SEP}{letter}{SEP}{region}{letter}",  # letter in the region field
        f"{digits}{SEP}{letter}{SEP}{region}999"[: len(tokens) + 3],  # region too long
        f"123456{SEP}{letter}{SEP}{region}",  # six digits only exist on WW plates
        f"{digits}{SEP}{MARK}{SEP}{region}",  # W where the letter goes
        f"{digits}{SEP}{SEP}{letter}{SEP}{region}",  # doubled separator
        f"{SEP}{letter}{SEP}{region}",  # empty digit field
        f"{digits}{SEP}{letter}{SEP}",  # empty region field
    ]
    for miss in near_misses:
        assert not grammar.accepts(miss), miss
    # The lenient parser forgives lost separators, but never a foreign letter or a
    # letter inside a digit field.
    assert parse_plate(near_misses[0]) is None
    assert parse_plate(near_misses[4]) is None


def test_fixed_near_misses() -> None:
    for miss in ["", SEP, "WW", "1234567-WW", "123-W", "123-WWW", "12-ب-123", "ب-1", "1-ب"]:
        assert not grammar.accepts(miss), miss


# --- normalisation ------------------------------------------------------------------
noisy_text = st.text(
    alphabet=st.sampled_from(
        list(DIGITS + LETTERS + "".join(_LETTER_VARIANTS.values()))
        + list(" -–_/.WwOoIlSBZ|!")
        + list("٠١٢٣٤٥٦٧٨٩")
        + list(NON_PLATE_LETTERS[:3])
    ),
    max_size=16,
)


@given(st.one_of(noisy_text, plates, st.text(max_size=12)))
def test_normalisation_is_idempotent(raw: str) -> None:
    once = grammar.normalize(raw)
    if once is not None:
        assert grammar.normalize(once) == once
        assert grammar.accepts(parse_plate(once).tokens)  # type: ignore[union-attr]


@given(plates)
def test_normalisation_tolerates_lost_separators(tokens: str) -> None:
    plate = Plate.from_tokens(tokens)
    assert plate is not None
    squashed = tokens.replace(SEP, "")
    assert grammar.normalize(squashed) == plate.text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("72 173 WW", "72173 WW"),  # OCR word splits inside a digit run
        ("72173 W W", "72173 WW"),
        ("248 30-أ-1", "24830-أ-1"),
        ("123 WW", "123 WW"),  # the architecture's temporary format is D{1,6} WW
        ("248-30-أ-1", None),  # a dash inside the digits is not a word split
        ("24830-أ-1-", "24830-أ-1"),
    ],
)
def test_lenient_parsing_rules(raw: str, expected: str | None) -> None:
    assert grammar.normalize(raw) == expected


# --- structure ------------------------------------------------------------------
def test_language_size_matches_the_specification() -> None:
    def size(fmt: PlateFormat) -> int:
        total = 1
        for f in fmt.fields:
            k = len(f.symbol_class.members)
            total *= sum(k**n for n in range(f.min_len, f.max_len + 1))
        return total

    # The two formats overlap nowhere (letter versus W after the separator).
    assert GRAMMAR.count_completions() == sum(size(f) for f in FORMATS)


def test_minimal_dfa_has_the_hand_derived_state_count() -> None:
    # start, 1..6 digits, separator (both formats), separator (WW only), letter,
    # second separator, 1 and 2 region digits, first and second W.
    assert GRAMMAR.num_states == 15
    again = PlateGrammar.compile(FORMATS)
    assert again.num_states == GRAMMAR.num_states


def test_allowed_symbols_follow_the_formats() -> None:
    assert GRAMMAR.allowed(GRAMMAR.start) == frozenset(DIGITS)
    assert GRAMMAR.allowed(GRAMMAR.run("12345-")) == frozenset(LETTERS + MARK)
    assert GRAMMAR.allowed(GRAMMAR.run("123456-")) == frozenset(MARK)
    assert GRAMMAR.allowed(GRAMMAR.run("123456")) == frozenset(SEP)
    assert GRAMMAR.allowed(GRAMMAR.run("1-ب-12")) == frozenset()
    assert GRAMMAR.possible_formats(GRAMMAR.run("12345")) == {"standard", "temporary"}
    assert GRAMMAR.possible_formats(GRAMMAR.run("123456")) == {"temporary"}
    assert GRAMMAR.accepting_formats(GRAMMAR.run("1-WW")) == {"temporary"}
    assert GRAMMAR.run("x") == DEAD
    assert GRAMMAR.step(DEAD, "1") == DEAD
    assert GRAMMAR.allowed(DEAD) == frozenset()
    assert grammar.transition(GRAMMAR.start, "7") != DEAD


def test_enumerate_completions_is_shortest_first_and_valid() -> None:
    first = list(grammar.enumerate_completions("", limit=50))
    assert len(first) == 50
    assert all(grammar.accepts(t) for t in first)
    assert [len(t) for t in first] == sorted(len(t) for t in first)
    completions = list(grammar.enumerate_completions("2483-ب-"))
    assert len(completions) == 10 + 100
    assert all(t.startswith("2483-ب-") for t in completions)
    assert list(grammar.enumerate_completions("x")) == []
    assert list(grammar.enumerate_completions("12-ب-34")) == ["12-ب-34"]


def test_segment_and_display() -> None:
    fmt, parts = GRAMMAR.segment("24830-ب-1")  # type: ignore[misc]
    assert fmt is STANDARD
    assert parts == {"digits": "24830", "sep1": "-", "letter": "ب", "sep2": "-", "region": "1"}
    fmt, parts = GRAMMAR.segment("72173-WW")  # type: ignore[misc]
    assert fmt is TEMPORARY
    assert grammar.to_display("72173-WW") == "72173 WW"
    assert GRAMMAR.format_of("72173-WW") == "temporary"
    assert GRAMMAR.format_of("72173") is None
    assert GRAMMAR.segment("nope") is None
    with pytest.raises(ValueError):
        grammar.to_display("nope")


def test_plate_validates_itself() -> None:
    assert Plate("24830", "ب", "1").text == "24830-ب-1"
    assert Plate("72173").text == "72173 WW"
    assert Plate("72173").format == "temporary"
    with pytest.raises(ValueError):
        Plate("24830", "ز", "1")
    with pytest.raises(ValueError):
        Plate("1234567")
    assert Plate.from_tokens("nope") is None


def test_random_plate_is_deterministic_for_a_seed() -> None:
    a = [grammar.random_plate(np.random.default_rng(7)) for _ in range(3)]
    b = [grammar.random_plate(np.random.default_rng(7)) for _ in range(3)]
    assert a == b
    rng = random.Random(3)
    sample = [grammar.random_plate(rng, "temporary") for _ in range(20)]
    assert all(t.endswith("-WW") for t in sample)
    assert all(grammar.random_plate(rng, STANDARD).count(SEP) == 2 for _ in range(20))
    with pytest.raises(KeyError):
        grammar.random_plate(rng, "diplomatic")
    with pytest.raises(TypeError):
        grammar.random_plate(object())


def test_symbol_classes_and_spec_validation() -> None:
    assert grammar.symbol_class("7") is SymbolClass.DIGIT
    assert grammar.symbol_class("ب") is SymbolClass.LETTER
    assert grammar.symbol_class(MARK) is SymbolClass.MARK
    assert grammar.symbol_class(SEP) is SymbolClass.SEP
    with pytest.raises(KeyError):
        grammar.symbol_class("x")
    with pytest.raises(ValueError):
        Field("bad", SymbolClass.DIGIT, 3, 2)
    with pytest.raises(ValueError):
        PlateGrammar.compile(())
    with pytest.raises(ValueError):
        PlateGrammar.compile((STANDARD, STANDARD))
    assert STANDARD.min_length == 5
    assert STANDARD.max_length == 10
    assert TEMPORARY.field("mark").is_constant
    assert STANDARD.field("sep1").is_separator
    with pytest.raises(KeyError):
        STANDARD.field("nope")


def test_a_new_format_is_one_declaration_away() -> None:
    diplomatic = PlateFormat(
        name="diplomatic",
        fields=(Field("digits", SymbolClass.DIGIT, 1, 3), Field("mark", SymbolClass.MARK, 1, 1)),
        display_separator=" ",
    )
    extended = PlateGrammar.compile((*FORMATS, diplomatic))
    assert extended.accepts("12W")
    assert not GRAMMAR.accepts("12W")
