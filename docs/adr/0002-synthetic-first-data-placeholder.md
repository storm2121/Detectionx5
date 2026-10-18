# ADR 0002: synthetic first, real data as a placeholder

Status: accepted (architect, 2026-10-18). Expand during M1.

## Context

The original training images are not on this machine, the firm's photos are private, and the public
README already states that OCR accuracy is not benchmarked. The platform must be fully runnable and
measurable without any real data, and the eventual real data must drop into a documented place.

## Decision

A deterministic synthetic plate generator provides crops, scenes, multi-view sets and a pseudo-real
set. `data/` holds only a layout, a README and a validator. Every synthetic metric is labelled as
synthetic. The repository never names the original dataset's hosting service.

## Consequences

Numbers in the README are honest but synthetic until real labels exist; the sim-to-real gap becomes
a visible page rather than a hidden assumption. Fonts must be open-licensed and bundled.
