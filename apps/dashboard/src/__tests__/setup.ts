// jsdom has no matchMedia; the theme store and the motion helpers ask for it.
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

// jsdom has no CSS matrix; D3 interpolates CSS transforms through one. An identity matrix is
// enough for tests, which check structure, not pixels.
if (
  typeof window !== 'undefined' &&
  typeof (window as { DOMMatrix?: unknown }).DOMMatrix !== 'function'
) {
  class IdentityMatrix {
    a = 1
    b = 0
    c = 0
    d = 1
    e = 0
    f = 0
    m41 = 0
    m42 = 0
    isIdentity = true
  }
  Object.assign(window, { DOMMatrix: IdentityMatrix, WebKitCSSMatrix: IdentityMatrix })
  Object.assign(globalThis, { DOMMatrix: IdentityMatrix, WebKitCSSMatrix: IdentityMatrix })
}
