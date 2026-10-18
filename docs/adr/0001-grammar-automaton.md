# ADR 0001: the plate grammar is one explicit automaton

Status: accepted (architect, 2026-10-18). Expand during M0.

## Context

Plate formats are currently encoded as regular expressions inside `normalize.py` and re-implied by
the segmentation and the vote. The rebuild needs the same formats in the generator, the constrained
decoder, the fusion candidate filter and the tests.

## Decision

`plate_reader/grammar.py` defines the two formats as a finite automaton with a transition function,
acceptance, normalisation, completion enumeration and random sampling. Every other module imports it.

## Consequences

One place to add a format; the constrained beam search prunes with the same object that validates
output. Hypothesis tests generate valid and near-miss strings from the automaton itself.
