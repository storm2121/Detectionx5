# ADR 0006: Vue 3 with TypeScript, D3 and ONNX Runtime Web

Status: accepted (architect, 2026-10-18); expanded during M0 by the executing agent (the
dashboard itself is M5 and M6).

## Context

The desktop GUI is Tkinter. The sibling project (Strata) uses React, so this project
deliberately uses a different front-end stack to broaden demonstrated skills. Plate photos
are sensitive, which makes on-device inference attractive.

## Decision

Vue 3, TypeScript strict, Vite, Pinia, Vue Router, PrimeVue with a custom theme and design
tokens, D3 for calibration and confusion views and the character heatmap, KaTeX for
equations, onnxruntime-web for an in-browser mode (WebGPU when available, WASM fallback),
pnpm, Storybook for Vue, Vitest, Playwright, axe. Parity with the Python pipeline is
enforced in CI on fixtures written by the Python side to `results/parity_fixtures.json`.

Constraints fixed now so M2 to M4 produce what M5 and M6 need:

- The CRNN ONNX graph outputs raw logits; temperature, softmax and the constrained beam
  run outside the graph (ADR 0003), so the TypeScript port has one well-defined
  post-processing step to match.
- The grammar's symbol order is the charset; the dashboard receives it from `GET /models`
  (or the model metadata JSON next to the ONNX file) instead of re-declaring it.
- The dashboard is served on host port 5174.

## Consequences

Two inference implementations to keep aligned (hence the parity tests); heavier front-end
tooling; a demo that works without a server and never uploads a photo.
