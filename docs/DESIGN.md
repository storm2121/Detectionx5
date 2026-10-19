# Design brief: the DetectionX5 console

Status: architect brief, 2026-10-19. The executing agent redesigns `apps/dashboard` against this
document. It extends `ARCHITECTURE.md` §12 and does not change what the console does, only how it
looks, moves and reads. The principles are Apple's (WWDC design talks, translated to the web): the
interface should feel like an extension of the person using it, not like a template.

## 1. What it must not look like

The console must not read as machine-generated. Remove, and never add:

- gradient hero blocks, purple-to-blue accents, glow effects, blurred colour blobs;
- rows of three identical cards with an icon, a title and a sentence each;
- emoji as icons, mixed icon sets, decorative icons that carry no meaning;
- rounded cards with drop shadows on everything; shadows are for floating surfaces only;
- generic copy: "Welcome", "Get started", "Powerful", "Seamless", "Unleash", exclamation marks;
- stat tiles with huge numbers and no context, spinners where a skeleton or the real content
  could appear, toasts for routine success;
- centred everything; dashboards are left-aligned, reading order top-left to bottom-right;
- a colour palette with more than one accent.

## 2. Foundations

- **Type.** The platform system stack: `-apple-system, BlinkMacSystemFont, "Segoe UI Variable",
  "Segoe UI", system-ui, sans-serif`, with `font-optical-sizing: auto`. Tabular figures for every
  number (`font-variant-numeric: tabular-nums`). Tracking is size-specific: display and titles
  tighten (`-0.02em` at 28px and above, `-0.01em` at 20px), body stays at `0`, captions and labels
  at 12px get `+0.01em`. Leading: 1.1 for titles, 1.45 for body, 1.3 for dense tables. Hierarchy
  comes from weight and size together: 600 for titles, 500 for labels, 400 for body. Sizes in rem;
  the layout scales with the user's text size. Arabic plate text uses `"Noto Naskh Arabic"` at a
  size that matches the Latin x-height, and is never italicised.
- **Colour.** One accent (a restrained blue, chosen for AA contrast on both themes), one success,
  one warning, one danger, and a neutral ramp of nine greys defined as tokens on `:root` and
  redefined for dark mode. Surfaces are near-white and near-black, not pure. Charts use the
  neutral ramp plus the accent; categorical series use a fixed, documented set of five hues with
  equal lightness. Confidence is shown as a single-hue ramp (light to accent), never red-to-green.
- **Space.** A 4px base scale (4, 8, 12, 16, 24, 32, 48, 64). Page gutter 24px on desktop, 16px at
  phone width. Content measure for text under 70 characters.
- **Shape.** Radius 6px for controls, 10px for panels, 16px for floating sheets. Borders are
  1px of a neutral token, hairline on high-density screens. No shadows on in-flow panels.
- **Materials.** The top bar and any floating sheet are translucent: `backdrop-filter:
  blur(20px) saturate(180%)` over a 60% surface, with a bright 1px top edge. Content scrolls under
  them. Never stack two translucent surfaces. Where a sticky header meets content, use a soft
  scroll-edge fade instead of a divider line. Respect `prefers-reduced-transparency` (solid
  surfaces, no blur) and `prefers-contrast: more` (solid surfaces with a defined border).
- **Icons.** One set, Lucide, at 16px and 20px, stroke 1.75, always with a text label or an
  accessible name. No icon-only buttons except in dense toolbars, and those get tooltips.

## 3. Motion

- **Respond on pointer-down.** Buttons and cards press (`scale(0.98)`, 100ms ease-out) the instant
  they are touched, not on release. No animation ever locks input.
- **Springs, not durations, for anything the user can touch.** Use the Motion library (`motion`
  package, Vue bindings or the vanilla `animate`) with critically damped springs by default
  (`bounce: 0`, `duration: 0.35`). Bounce (`0.2`) only after a flick or a drag release.
- **Interruptible.** Every transition starts from the element's current on-screen value; a sheet
  the user grabs mid-close follows the pointer. No CSS keyframes on gesture-driven elements.
- **Spatial consistency.** Panels exit the way they entered. Popovers scale from their trigger
  (`transform-origin` at the trigger). Mirror easings on reversible transitions.
- **Drag and drop** on the Read page tracks the pointer 1:1 with Pointer Events and pointer capture,
  respects the grab offset, rubber-bands at the drop zone's edges, and hands the release velocity to
  a spring that settles the thumbnail into its slot.
- **Reduced motion.** Under `prefers-reduced-motion: reduce`, every spring and slide becomes a
  200ms opacity cross-fade; the heatmap and charts render without entrance animation.
- **Only `transform` and `opacity` animate.** Chart updates use D3 transitions on data joins with
  the same spring-like easing, never re-mounting.

## 4. Craft rules

- Every number has a unit or a context word, uses tabular figures and the same decimal precision
  within a table. Intervals read `25% (0 to 50)`; the console never shows a bare point estimate.
- Status, completion, warning and error feedback are distinct in colour and wording. Errors say what
  happened and what to do. Inline validation, never on submit.
- Empty states say what will appear here and how to make it appear, in one sentence, with the one
  action that does it.
- Loading uses skeletons shaped like the content. Long jobs show progress with a count and a rate.
- Keyboard: every control reachable, visible focus ring (2px accent, 2px offset), Escape closes
  sheets, Enter submits. Touch targets at least 44px at phone width.
- Wayfinding: the top bar names the page; the Read page is the home and the first item; every other
  page is one click away and says what it holds in its title: "Review queue (3 waiting)",
  "Evaluation", "Models", "Methods". No "Home", no "Dashboard".
- Copy is plain and specific: "Read plate", "Send to review", "Export 3 corrections". Sentence
  case everywhere. No marketing adjectives. No exclamation marks.
- Light and dark themes with equal care; test both at phone width and at 1440px.

## 5. The pages

- **Read** is the product. One column at phone width, two at desktop: the photos and their boxes on
  the left, the result on the right. The result card shows the plate large in both scripts, the
  calibrated confidence as a ramp bar with its number, the prediction set as chips, and the
  character heatmap directly under the plate with the same letter spacing as the plate text so the
  columns align. Per-view hypotheses sit in a collapsible section. Server and in-browser modes are a
  segmented control, with the parity indicator a small check beside it. Synthetic sample photos
  are gone from this page (see the task brief).
- **Review queue**: a list with the photo thumbnail, the proposed read, the set, and a text field
  that accepts the correction inline; the export is one button with the count in its label.
- **Jobs**: a table with progress bars that fill with the real rate; SSE updates animate the bar
  with a spring, not a jump.
- **Evaluation** and **Models**: results tables first, charts second; D3 calibration curve and
  confusion matrix in the neutral ramp with the accent for the model; the sim-to-real gap shown as
  two bars with their intervals, labelled with the set they come from.
- **Methods**: equations in KaTeX with a 70-character measure and generous leading.

## 6. Deliverables

A tokens file (`src/styles/tokens.css`) with light and dark values; the components restyled to
use only tokens; Storybook stories showing every component in both themes; Playwright screenshots
of every page in both themes at 1440px and at 390px saved under `docs/images/`; the axe checks and
the bundle check still green; a short `docs/DESIGN_NOTES.md` listing every decision that departs
from this brief and why.
