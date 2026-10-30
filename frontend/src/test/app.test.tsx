import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";

import { renderApp } from "@/test/render";
import type { ModuleStatusItem, SourceOut, SystemStatus } from "@/types/api";

const MODULES: ModuleStatusItem[] = [
  {
    key: "overview",
    label: "Overview",
    route: "/",
    phase: "Phase 4",
    status: "scaffolded",
    summary: "Global fire activity and intelligence summary.",
    planned: ["Detections split by sensor", "Daily detection trend"],
  },
  {
    key: "calendar",
    label: "Burning Calendar",
    route: "/calendar",
    phase: "Phase 5",
    status: "scaffolded",
    summary: "Historical burning activity by day, month and year.",
    planned: ["Daily / weekly / monthly / annual views"],
  },
  {
    key: "settings",
    label: "Settings",
    route: "/settings",
    phase: "Phase 1",
    status: "in_progress",
    summary: "System health, data sources and administration.",
    planned: ["Data source registry and freshness"],
  },
];

const STATUS: SystemStatus = {
  app_name: "FIREWATCH X",
  app_version: "0.1.0",
  environment: "test",
  phase: "1",
  phase_name: "Foundation",
  server_time: "2026-10-30T00:00:00Z",
  uptime_seconds: 42,
  database: {
    dialect: "sqlite",
    connected: true,
    postgis: null,
    latency_ms: 1.2,
    error: null,
  },
  data: {
    freshness: "no_data",
    freshness_reason: "FIRMS_MAP_KEY is not configured, so no NASA observations can be retrieved.",
    firms_configured: false,
    sources_registered: 8,
    observations_stored: null,
    last_ingested_at: null,
    last_observation_at: null,
  },
  capabilities: {
    authentication: false,
    rate_limiting: false,
    ai_assistant: false,
    reports: false,
    ingestion: false,
    spatial: false,
  },
  modules: MODULES,
};

const SOURCES: SourceOut[] = [
  {
    code: "MODIS_SP",
    sensor: "MODIS",
    satellite: "Terra/Aqua",
    processing_level: "SP",
    description: "MODIS standard processing.",
    status: "not_ingested",
  },
];

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/system/status")) return jsonResponse(STATUS);
      if (url.includes("/api/v1/system/modules")) return jsonResponse(MODULES);
      if (url.includes("/api/v1/system/sources")) return jsonResponse(SOURCES);
      return jsonResponse({ error: { code: "not_found", message: "nope", details: {} } }, 404);
    }),
  );
});

describe("application shell", () => {
  it("renders every navigation destination", async () => {
    renderApp("/");

    const nav = await screen.findByRole("navigation", { name: /primary navigation/i });
    expect(within(nav).getByRole("link", { name: /overview/i })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: /burning calendar/i })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: /global fire map/i })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: /ai assistant/i })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: /settings/i })).toBeInTheDocument();
  });

  it("shows the delivery phase and honesty disclaimer", async () => {
    renderApp("/");

    expect(await screen.findByText(/phase 1 \/ 9/i)).toBeInTheDocument();
    expect(
      screen.getByText(/thermal anomalies, not confirmed wildfires/i),
    ).toBeInTheDocument();
  });

  it("reports missing NASA data instead of inventing activity", async () => {
    renderApp("/");

    expect(await screen.findByText(/no nasa data/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/no fire activity to display/i)).toBeInTheDocument();
    });
    // Freshness reason comes from the API, not the component.
    expect(
      screen.getAllByText(/FIRMS_MAP_KEY is not configured/i).length,
    ).toBeGreaterThan(0);
  });

  it("renders the module registry status in the sidebar", async () => {
    renderApp("/");

    await waitFor(() => {
      expect(screen.getByText(/0 of 3 modules operational/i)).toBeInTheDocument();
    });
  });

  it("renders a not-found view for unknown routes", async () => {
    renderApp("/does-not-exist");

    expect(await screen.findByText(/no such view/i)).toBeInTheDocument();
  });
});

describe("settings module", () => {
  it("lists the FIRMS source registry with no ingestion claimed", async () => {
    renderApp("/settings");

    expect(await screen.findByText("MODIS_SP")).toBeInTheDocument();
    expect(screen.getByText(/not ingested/i)).toBeInTheDocument();
    expect(screen.getByText(/^FIRMS_MAP_KEY$/)).toBeInTheDocument();
  });

  it("marks unbuilt capabilities as not built", async () => {
    renderApp("/settings");

    expect(await screen.findByText(/authentication & rbac/i)).toBeInTheDocument();
    expect(screen.getAllByText(/not built/i).length).toBeGreaterThan(0);
  });
});
