/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional absolute API origin. Empty in development (Vite proxies /api). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
