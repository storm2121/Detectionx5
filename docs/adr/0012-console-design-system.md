# ADR 0012: the console's design system: tokens, headless controls, Motion and Lucide

Status: accepted (executing agent, 2026-10-19, under the architect's design brief
`docs/DESIGN.md`). Deviates from ARCHITECTURE §12 and ADR 0006, which name "PrimeVue
components with a custom theme and design tokens".

## Context

The design brief sets the console's foundations: the platform's system type stack, one
accent, a nine-step neutral ramp, a 4 px space scale, translucent chrome, controls that
respond on pointer-down, springs for everything a user can touch, interruptible
transitions, and reduced-motion, reduced-transparency and higher-contrast variants. It
allows PrimeVue to stay only if it is fully themed through the console's tokens.

The console used five PrimeVue components (Button, InputText, SelectButton, Select,
ToggleSwitch) on an Aura preset. Aura brings its own design tokens, CSS transitions on
every control, box-shadow focus rings, shadows on overlays and its own spacing; theming
all of that through the console's tokens would mean overriding most of the preset and
still fighting CSS transitions that cannot be grabbed mid-flight or driven by a spring.

## Decision

- PrimeVue and its theme package are removed. The five controls are replaced by small
  headless components in `apps/dashboard/src/components/ui/` (button, text field, select
  on the native element, segmented control, switch, disclosure), styled only with the
  tokens in `apps/dashboard/src/styles/tokens.css`.
- Motion (the `motion` package, its framework-free `animate`) drives every animation a
  user can touch: critically damped springs by default, a little bounce only after a drag
  release, each animation starting from the element's current on-screen value. Under
  `prefers-reduced-motion: reduce` each becomes a short opacity cross-fade.
- Lucide (`lucide-vue-next`) is the only icon set, at 16 and 20 px with a 1.75 stroke,
  always beside a text label or with an accessible name.
- D3 stays for scales, colour interpolation and the charts' data joins, with an eased
  transition that approximates the critically damped spring.

## Consequences

Every pixel of the console comes from one tokens file, so light, dark, reduced
transparency and higher contrast are each one block of custom properties. The bundle
loses PrimeVue's runtime and styles and gains Motion's animation engine and only the
Lucide icons the pages import. Accessibility that PrimeVue provided (roles, keyboard
handling) is now the console's own code and is covered by unit tests, Storybook's axe
checks and the Playwright axe runs.
