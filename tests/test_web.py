"""The assets the browser runtime reads from Python stay in step with the Python side."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from plate_reader.crnn.charset import CHARSET_ID, CLASSES
from plate_reader.grammar import DEAD, GRAMMAR, SYMBOLS, accepts
from plate_reader.web import (
    GRAMMAR_JSON,
    OPENCV_CASES,
    grammar_export,
    opencv_cases,
    write_web_assets,
)


def test_the_committed_grammar_is_the_current_automaton() -> None:
    committed = json.loads(GRAMMAR_JSON.read_text(encoding="utf-8"))
    assert committed == grammar_export(), "run `uv run plate export web` and commit the result"
    assert committed["symbols"] == list(SYMBOLS)
    assert committed["charset"] == list(CLASSES)
    assert committed["charset_id"] == CHARSET_ID
    assert committed["dead"] == DEAD


def _walk(table: dict[str, object], tokens: str) -> bool:
    transitions = table["transitions"]
    accepting = table["accepting"]
    assert isinstance(transitions, list)
    assert isinstance(accepting, list)
    state = int(table["start"])  # type: ignore[arg-type]
    for symbol in tokens:
        state = transitions[state][SYMBOLS.index(symbol)]
        if state == DEAD:
            return False
    return bool(accepting[state])


@pytest.mark.parametrize(
    "tokens", ["24830-ب-1", "1-أ-12", "72173-WW", "123456-WW", "24830-ب", "2483-WWW", "ب-1", ""]
)
def test_the_exported_table_accepts_what_the_grammar_accepts(tokens: str) -> None:
    assert _walk(grammar_export(), tokens) == accepts(tokens)


def test_the_committed_opencv_cases_are_current() -> None:
    committed = json.loads(OPENCV_CASES.read_text(encoding="utf-8"))
    fresh = opencv_cases()
    assert committed["resize"] == fresh["resize"], "run `uv run plate export web`"
    assert committed["grey"] == fresh["grey"]


def test_opencv_cases_decode_to_what_opencv_does() -> None:
    cases = opencv_cases()
    for case in cases["resize"]:
        sw, sh, channels = case["source"]
        dw, dh = case["target"]
        shape = (sh, sw, channels) if channels == 3 else (sh, sw)
        src = np.frombuffer(base64.b64decode(case["src"]), np.uint8).reshape(shape)
        flag = cv2.INTER_LINEAR if case["interpolation"] == "linear" else cv2.INTER_AREA
        out = cv2.resize(src, (dw, dh), interpolation=flag)
        assert base64.b64encode(out.tobytes()).decode() == case["expected"]


def test_write_web_assets(tmp_path: Path) -> None:
    written = write_web_assets(tmp_path / "grammar.json", tmp_path / "cases.json")
    assert [p.name for p in written] == ["grammar.json", "cases.json"]
    assert json.loads(written[0].read_text(encoding="utf-8"))["start"] == GRAMMAR.start
