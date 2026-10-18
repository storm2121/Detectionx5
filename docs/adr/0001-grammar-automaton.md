# ADR 0001: the plate grammar is one explicit automaton

Status: accepted (architect, 2026-10-18); expanded during M0 by the executing agent.

## Context

Plate formats were encoded as regular expressions inside `normalize.py` and re-implied by
the segmentation and the vote (`MAX_MAIN_DIGITS = 5`, `MAX_REGION_DIGITS = 2` in
`pipeline.py`, alphabets in `ocr.py`). The rebuild needs the same formats in the
generator, the constrained CTC decoder, the fusion candidate filter and the tests. A
regex can only answer "does the whole string match"; constrained decoding needs "which
symbols may follow this prefix" and "can this prefix still become a plate".

## Options considered

1. Keep regexes and add a hand-written prefix checker for decoding: two definitions that
   drift.
2. A hand-coded DFA: compact, but adding a format means re-deriving states by hand.
3. Declarative formats compiled to a minimal DFA: one definition, mechanically correct.

## Decision

Option 3, in `plate_reader/grammar.py`:

- Formats are `PlateFormat`s, ordered sequences of `Field(name, symbol class, min, max)`:
  standard = `digits{1,5} SEP letter SEP region{1,2}`, temporary = `digits{1,6} SEP W{2}`,
  letters `أ ب د ه و ط`.
- Compilation: NFA over states `(format, field, count)` with epsilon moves between fields,
  subset construction, removal of states that cannot reach acceptance (so every live
  state is a viable prefix, the invariant constrained decoding relies on), Moore partition
  refinement, breadth-first renumbering for deterministic state ids. The result has 15
  states, which matches the hand derivation in `tests/test_grammar.py`.
- One separator symbol `-` in the canonical *token* spelling for both formats
  (`24830-ب-1`, `72173-WW`), because the recogniser has a single separator class; the
  *display* spelling (`72173 WW`) is derived from each format's display separator.
- The fixed symbol order `SYMBOLS` (digits, letters, `W`, separator) is the CRNN charset
  with the CTC blank prepended.
- API: `accepts`, `step`/`step_index`/`allowed` (the transition function for the beam
  search), `enumerate_completions`, `count_completions`, `segment`, `random_plate`,
  `normalize` and `parse` (lenient, through `normalize.py`), and the `Plate` dataclass,
  which refuses to exist for a string the automaton rejects.
- `normalize.py` keeps the character folding (Unicode letter variants, Arabic-Indic
  digits, dash-like separators) and replaces its two regexes with a tokeniser plus a DFA
  simulation that may insert a lost separator at a digit/letter boundary and treats a
  whitespace-only gap between two digits (or two `W`) as an OCR word split. Lookalike
  repair (`O` to `0`) maps to digit symbols, which the automaton only accepts in digit
  fields, so repair can never leak into the letter field.

## Behaviour changes, recorded

- Temporary plates now accept 1 to 6 digits, as `ARCHITECTURE.md` §5 specifies; the old
  regex accepted only 5 or 6. Open question for the architect: confirm the digit range
  with the firm's experts.
- A whitespace-only gap inside the digits of a standard plate is now repaired
  (`248 30-أ-1`); before, only temporary plates were repaired this way. A dash inside the
  digits is still rejected.
- All 26 parametrised cases of the original `tests/test_normalize.py` pass unchanged.

## Consequences

One place to add a format (a test adds a third format in one declaration). The
constrained beam search prunes with the same object that validates output, fusion filters
candidates with it, the generator samples from it, and hypothesis tests generate valid
plates and near-misses from it and cross-check the DFA against a regex compiled
independently from the same specification.
