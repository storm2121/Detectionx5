// jsdom has no matchMedia; PrimeVue and the theme store ask for it.
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string): MediaQueryList =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => undefined,
        removeListener: () => undefined,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        dispatchEvent: () => false,
      }) as MediaQueryList,
  })
}

// jsdom does not scroll; the router's scroll behaviour calls it on every navigation.
if (typeof window !== 'undefined') {
  window.scrollTo = (() => undefined) as typeof window.scrollTo
}
