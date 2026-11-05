import "@testing-library/jest-dom/vitest";

import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

import { useUiStore } from "@/store/ui";

beforeEach(() => {
  // Deterministic period: fixtures live around 2026-10-29.
  useUiStore.setState({
    dateRange: { preset: "7d", start: "2026-10-29", end: "2026-11-04" },
  });
});

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  vi.restoreAllMocks();
});

// jsdom logs a "Not implemented" error for canvas contexts, which Vitest treats
// as an unhandled error. The app already degrades gracefully without 2D.
Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
  configurable: true,
  value: () => null,
});
