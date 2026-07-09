/// <reference types="vite/client" />
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_WS_BASE?: string;
  readonly VITE_PLUGIN_MODE?: 'standalone' | 'quantcell';
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
