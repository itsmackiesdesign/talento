/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Absolute API origin. Empty means same-origin via the Vite dev proxy. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
