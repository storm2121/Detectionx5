/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the plate service; the dev server and nginx proxy `/api` to it. */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
