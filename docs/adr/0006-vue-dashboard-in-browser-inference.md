# ADR 0006: Vue 3 with TypeScript, D3 and ONNX Runtime Web

Status: accepted (architect, 2026-10-18). Expand during M5 and M6.

## Context

The desktop GUI is Tkinter. The sibling project (Strata) uses React, so this project deliberately
uses a different front-end stack to broaden demonstrated skills. Plate photos are sensitive, which
makes on-device inference attractive.

## Decision

Vue 3, TypeScript strict, Vite, Pinia, Vue Router, PrimeVue with a custom theme, D3 for calibration
and confusion views and the character heatmap, KaTeX for equations, onnxruntime-web for an in-browser
mode with WASM fallback, Storybook for Vue, Vitest, Playwright, axe. Parity with the Python pipeline
is enforced in CI on fixtures.

## Consequences

Two inference implementations to keep aligned (hence the parity tests); heavier front-end tooling;
a demo that works without a server and never uploads a photo.
