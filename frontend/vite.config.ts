/// <reference types="vitest" />
import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Ports are deliberately non-default: 5173/8000/8100 are frequently occupied on
 * developer machines. Override with `--port` / VITE_PROXY_TARGET if needed.
 */
const WEB_PORT = Number(process.env.VITE_PORT ?? 5273);
const API_TARGET = process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8200";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: WEB_PORT,
    strictPort: true,
    proxy: {
      // A pooled upstream socket can stall for seconds after the browser aborts
      // a request (React StrictMode double-mounts do this in dev), so proxied
      // calls get their own connection instead of reusing a poisoned one.
      "/api": { target: API_TARGET, changeOrigin: true, agent: false },
      "/health": { target: API_TARGET, changeOrigin: true, agent: false },
      "/ready": { target: API_TARGET, changeOrigin: true, agent: false },
    },
  },
  preview: {
    port: WEB_PORT,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
