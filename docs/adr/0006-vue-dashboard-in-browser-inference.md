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

## Implementation notes (M5, executing agent)

- Versions are pinned exactly (`apps/dashboard/package.json`, `pnpm-lock.yaml`) to the
  majors the console was written and verified against: Vue 3.5, Vue Router 4, Pinia 3,
  PrimeVue 4 with `@primeuix/themes`, Vite 6, Vitest 3, Storybook 8.6, TypeScript 5.8,
  Playwright 1.53. Newer majors exist; moving to them is a separate, tested change.
- pnpm runs through Node's corepack (`corepack pnpm@9.15.9`), so nothing is installed
  globally; `just dashboard`, `dashboard-check` and `dashboard-e2e` wrap it.
- The browser always calls `/api/...`: Vite's dev server and the container's nginx forward
  it to the service, so there is no CORS configuration and one image serves any host.
- The Evaluation, Models and Methods pages render the committed `results/*.json` through
  `GET /results/{name}` instead of bundling them, so the console shows the results of the
  models the service actually loaded. Every page with a number carries the synthetic label
  (a footer line on every page, and a note on each page that shows metrics).
- Design tokens live in `src/theme/tokens.css` (CSS custom properties, light and dark); the
  PrimeVue preset maps Aura onto the same slate and teal palette and darkens the primary
  colour in light mode so that text on buttons keeps WCAG AA contrast. The D3 charts read
  the tokens, so they follow the theme; the theme store applies the scheme synchronously so
  the charts never draw with the previous palette.
- Plate text is shown with `unicode-bidi: isolate-override`: plain bidi reorders
  `24830-ب-1` (a digit after an Arabic letter becomes an Arabic number), and the only Arabic
  in a plate is one letter, so overriding is safe.
- Accessibility is checked by tests: Playwright runs axe (WCAG 2.1 A and AA) on every
  page in both themes at desktop and phone width and fails on any violation, and checks that
  no page scrolls sideways.

## Implementation notes (M6, executing agent)

- The in-browser runtime (`apps/dashboard/src/inference`) ports every step the Python
  pipeline takes between a decoded photo and a read: Ultralytics' letterbox, OpenCV's
  `cvtColor` and `resize` (INTER_LINEAR with OpenCV's fixed-point weights and the rounding of
  its SIMD vertical pass, INTER_AREA with exact block averages and float area weights), the
  detector's padding, cropping and de-duplication, the temperature log-softmax, the
  grammar-constrained prefix beam search, the beam posterior and conformal set, CPython's
  `math.fsum`, the Levenshtein alignment and the probabilistic fusion. The pixel operations
  are checked byte for byte against reference cases written by OpenCV
  (`tests/fixtures/web/opencv_cases.json`); everything else against
  `results/parity_fixtures.json`, which now records the CRNN's 8-bit input for every crop.
- The plate automaton reaches the browser as `src/inference/grammar.json`, exported by
  `plate export web`; a Python test fails when the committed copy differs from the grammar.
- ONNX Runtime Web (pinned at 1.22) runs WebGPU when the browser offers an adapter and the
  single-threaded WebAssembly backend otherwise (a static page without cross-origin
  isolation cannot use threads). Its WebAssembly binary is bundled by Vite; the models and
  the parity fixtures are copied into the console's static files at build time, so a read in
  the browser needs no service and uploads nothing.
- Parity is visible, not assumed: switching the Read page to the in-browser mode runs the
  fixtures on the chosen backend and shows the outcome next to the toggle; `/parity` lists
  every fixture with its largest differences; the Playwright parity test fails CI when any
  fixture is out of the tolerances the fixtures state.
