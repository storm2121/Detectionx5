import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

/**
 * The console's PrimeVue theme: Aura's structure on the slate and teal palette of
 * tokens.css. Primary colours are darkened in light mode and lightened in dark mode so that
 * text on primary buttons keeps WCAG AA contrast (Aura's defaults do not).
 */
const slate = {
  0: '#ffffff',
  50: '{slate.50}',
  100: '{slate.100}',
  200: '{slate.200}',
  300: '{slate.300}',
  400: '{slate.400}',
  500: '{slate.500}',
  600: '{slate.600}',
  700: '{slate.700}',
  800: '{slate.800}',
  900: '{slate.900}',
  950: '{slate.950}',
}

export const ConsolePreset = definePreset(Aura, {
  components: {
    // Aura's unselected toggle text (slate 500 on slate 100) is under 4.5:1.
    togglebutton: {
      colorScheme: {
        light: {
          root: { color: '{surface.600}', hoverColor: '{surface.800}' },
          icon: { color: '{surface.600}', hoverColor: '{surface.800}' },
        },
      },
    },
  },
  semantic: {
    primary: {
      50: '{teal.50}',
      100: '{teal.100}',
      200: '{teal.200}',
      300: '{teal.300}',
      400: '{teal.400}',
      500: '{teal.500}',
      600: '{teal.600}',
      700: '{teal.700}',
      800: '{teal.800}',
      900: '{teal.900}',
      950: '{teal.950}',
    },
    focusRing: { width: '2px', style: 'solid', color: '{blue.600}', offset: '2px' },
    colorScheme: {
      light: {
        surface: slate,
        primary: {
          color: '{primary.700}',
          contrastColor: '#ffffff',
          hoverColor: '{primary.800}',
          activeColor: '{primary.900}',
        },
        highlight: {
          background: '{primary.50}',
          focusBackground: '{primary.100}',
          color: '{primary.800}',
          focusColor: '{primary.900}',
        },
      },
      dark: {
        surface: slate,
        primary: {
          color: '{primary.300}',
          contrastColor: '{slate.950}',
          hoverColor: '{primary.200}',
          activeColor: '{primary.100}',
        },
        highlight: {
          background: 'color-mix(in srgb, {primary.400}, transparent 84%)',
          focusBackground: 'color-mix(in srgb, {primary.400}, transparent 76%)',
          color: 'rgba(255,255,255,.87)',
          focusColor: 'rgba(255,255,255,.87)',
        },
      },
    },
  },
})

export const DARK_CLASS = 'dx-dark'
