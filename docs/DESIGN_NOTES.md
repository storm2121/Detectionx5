# Design notes: where the console departs from the brief, and why

The console follows `docs/DESIGN.md`. This page lists every decision that departs from the
brief, or reads it in a way a reviewer might not expect, with the reason. The architecture
change itself (PrimeVue out; headless controls, Motion and Lucide in) is ADR 0012.

## Foundations

- **The type stack names the optical-size instances.** Chromium on Windows does not resolve
  the family name "Segoe UI Variable", and it ignores `font-optical-sizing` on that font's
  named instances (measured: the same text has identical widths at 12 and 40 px with optical
  sizing on and off). The stack therefore names `Segoe UI Variable Text` for body text,
  `Display` for titles and `Small` for captions, behind `-apple-system` and
  `BlinkMacSystemFont`, with the brief's family kept as a fallback; `font-optical-sizing:
  auto` stays for platforms that honour it.
- **Arabic plate text.** Noto Naskh Arabic (bundled, OFL) is declared for Arabic code points
  only and leads every font stack, so the plate letter is in Naskh wherever it appears and
  Latin text never touches it. `size-adjust` on that face brings the letters' bodies (ب, د, ه
  measured against the system face's x-height) to the Latin x-height. `font-synthesis: none`
  keeps it from ever being slanted or emboldened.
- **"The plate large in both scripts"** is read as the plate's Latin digits and its Arabic
  letter, each in its own face at the same x-height. No Latin transliteration of the letter is
  shown: the plate grammar defines none, and inventing one would be a claim the code does not
  make.
- **Tabular figures everywhere**, as the brief says, including the large plate digits and the
  confidence figure (data-visualisation practice would use proportional figures for big
  standalone numbers; the brief rules).
- **One accent, two steps in dark mode.** The accent is one blue. In dark mode the step used
  for text, marks and the focus ring is lighter than the step behind white text (primary
  buttons, the tab badge), because no single blue passes AA both as text on the dark surface
  and as a background for white text.
- **Categorical hues are defined, not yet used.** The five equal-lightness hues are in the
  tokens and pass the dataviz validator in their order, but no chart needs more than one
  series and a neutral reference: the sim-to-real chart draws synthetic bars in the neutral
  ramp and real bars in the accent, which is the brief's "neutral ramp plus the accent".
- **The detector's box over a photo** is drawn in the accent on a light halo rather than in a
  highlight colour, so the palette keeps one accent.
- **Hairlines.** Borders are one pixel, and half a pixel on screens of two device pixels per
  CSS pixel or more.

## Navigation and layout

- **At phone width the pages move to a bottom tab bar** (translucent, every tab at least
  44 px, icon over a short name), and the top bar shows the page's name. A horizontally
  scrolling row of six links would hide some pages; the tab bar keeps every page one tap
  away. The two translucent bars never overlap, so no translucent surface stacks on another.
- **The review queue's count** comes from a new `GET /review/summary`; the navigation says
  "Review queue (3 waiting)" or "(none waiting)", and the export button "Export 3
  corrections" or "No corrections to export".
- **Browser parity** stays off the navigation, as before: it is reached from the parity check
  beside the Read page's mode control.
- **The result panel is sticky** at desktop width, so the read stays in view beside the
  photos while the page scrolls.
- **Content is a centred column** of at most 80 rem at wide widths; everything in it is
  left-aligned and reads top-left to bottom-right.

## Motion

- **Motion's framework-free `animate`**, not its Vue bindings: each component animates its own
  element, and every animation starts from the element's current value, which is what makes
  them interruptible.
- **Press feedback** is the brief's 100 ms ease-out scale on pointer-down; the release is a
  critically damped spring. Under reduced motion the press is a brief dim instead of a scale.
- **Drag and drop** is the photo tray's reordering. Files dragged in from the operating system
  use the browser's own drag events, which pointer events cannot drive; once in the tray, a
  photo is dragged with pointer events and pointer capture, 1:1 from the grab point,
  rubber-banded at the tray's edges, and released into a spring that carries the pointer's
  velocity (bounce 0.2, the brief's after-a-drag value). The photos it passes slide on
  critically damped springs. On touch, a photo is picked up after a short press, so a swipe
  over the tray still scrolls the page. Arrow keys, Home and End move a focused photo, and a
  live region announces the new position. Escape cancels a drag.
- **There are no sheets.** The console never needed a floating sheet, so the sheet radius
  token is defined but unused; the only floating surface is the icon button's tooltip, which
  grows from its trigger and is the one place, with a lifted photo, that carries a shadow.
- **Charts.** Charts whose marks join data (the calibration curve, the sim-to-real bars) use
  D3 joins with transitions eased on a critically damped spring curve and move marks by
  transform or opacity only; the calibration curve's line cross-fades, since a path's shape
  cannot change by a transform. Marks that live in tables (interval bars, confusion cells,
  heatmap cells) are updated in place by Vue and animate their transform or opacity with a CSS
  transition on a cubic-bézier close to the same curve, rather than through D3. The training
  curve does not change after it draws, so it has no transition. Under reduced motion charts
  draw without entrance or transition.
- **Theme changes cross-fade** through an opacity view transition where the browser supports
  it, so the brightness changes gently; under reduced motion the theme simply switches.
- **Skeletons pulse** with a CSS keyframe on opacity; they are not gesture-driven, and under
  reduced motion they are still.

## Copy and numbers

- **Numbers without an interval say why.** The console never shows a bare point estimate:
  metrics carry "25% (0 to 50)". Where the source has no interval (a single Ultralytics
  validation pass, a training run's validation score), the text says "one pass, no interval"
  beside the number instead. A single read's calibrated confidence is a probability, not an
  estimate of a rate, so it has no interval.
- **Low confidence is said, not recoloured.** The confidence bar stays one hue; a read under
  the review threshold gets the words "under the review threshold" and the threshold tick.
- **Plate strings inside running text** (the correction field's example and placeholder) are
  wrapped in left-to-right override marks, for the same reason the plate class overrides
  bidi: plain bidi would show `24830-ب-1` as `24830-1-ب`.
- **The synthetic label stays on every page** (AGENT_RULES §1.3) as a quiet note in the flow,
  not an alarm, and in the footer.

## Deliverables

- **Storybook renders every story in both themes at once**, side by side (stacked when the
  canvas is narrow); the theme toolbar can isolate one.
- **Screenshots** (`docs/images/console-<page>-<theme>-<width>.png`) are whole pages at
  device scale 1, captured by `just dashboard-screenshots` against a running stack, so the
  folder stays small. The phone captures size the viewport to the page, which puts the tab bar
  at the bottom of the image, where a person sees it.
- **The bundle check is new** (`scripts/check-bundle.mjs`, run by `pnpm build`): what a first
  visit downloads must stay inside a gzipped budget set below what the console shipped before
  the redesign, and no component library may come back into the bundle.
