import { describe, expect, it, beforeEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock, makeStatus } from "@/test/fixtures";

beforeEach(() => {
  installFetchMock();
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

    expect(await screen.findByText(/phase 3 \/ 9/i)).toBeInTheDocument();
    expect(screen.getByText(/thermal anomalies, not confirmed wildfires/i)).toBeInTheDocument();
  });

  it("reports missing NASA data instead of inventing activity", async () => {
    renderApp("/");

    expect(await screen.findByText(/no nasa data/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/no fire activity to display/i)).toBeInTheDocument();
    });
    // Freshness reason comes from the API, not the component.
    expect(screen.getAllByText(/FIRMS_MAP_KEY is not configured/i).length).toBeGreaterThan(0);
  });

  it("renders the module registry status in the sidebar", async () => {
    renderApp("/");

    await waitFor(() => {
      expect(screen.getByText(/1 of 4 modules operational/i)).toBeInTheDocument();
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

    expect((await screen.findAllByText("MODIS_SP")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not ingested/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^FIRMS_MAP_KEY$/).length).toBeGreaterThan(0);
  });

  it("reports the security, reports and assistant capabilities as available", async () => {
    renderApp("/settings");

    expect(await screen.findByText(/authentication & rbac/i)).toBeInTheDocument();
    expect(screen.getAllByText(/available/i).length).toBeGreaterThan(0);
  });

  it("disables live ingestion when no FIRMS key is configured", async () => {
    renderApp("/settings");

    const runButton = await screen.findByRole("button", { name: /run window/i });
    expect(runButton).toBeDisabled();
    expect(screen.getByText(/key missing/i)).toBeInTheDocument();
  });
});

describe("overview with stored observations", () => {
  it("shows real counts and labels synthetic fixture data", async () => {
    installFetchMock({
      status: makeStatus({
        freshness: "delayed",
        observations_stored: 9,
        synthetic_observations: 9,
        freshness_reason: "All stored observations come from the labelled synthetic fixture.",
      }),
      dashboard: {
        period: { start_date: null, end_date: null },
        detections: { total: 9, modis: 5, viirs: 4, frp_mw: 105.3 },
        matches: { total: 5, probable: 1, possible: 2 },
        events: 2,
        scope: { bbox: [2.5, 4, 14.7, 13.9], start_date: "2026-10-29", end_date: "2026-10-30" },
        data: makeStatus({ observations_stored: 9, synthetic_observations: 9 }).data,
        note: "Counts are satellite thermal detections, not the number of fires.",
      },
    });

    renderApp("/");

    expect(await screen.findByText(/demo data only/i)).toBeInTheDocument();
    expect(screen.getAllByText("9").length).toBeGreaterThan(0);
    expect(screen.getByText(/5 MODIS · 4 VIIRS/i)).toBeInTheDocument();
  });
});
