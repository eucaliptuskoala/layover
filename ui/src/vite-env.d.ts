/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_BOOKING_TIMEOUT_MS?: string;
  readonly VITE_TEMPORAL_UI_URL?: string;
  readonly VITE_TEMPORAL_NAMESPACE?: string;
}
