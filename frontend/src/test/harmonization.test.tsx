import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { EVENTS, FIXTURE_SUMMARY, MATCHES, installFetchMock } from "@/test/fixtures";

describe("sensor intelligence (Phase 3)", () => {
  it("reports an honest empty state before any observation exists", async () => {
    installFetchMock();
    renderApp("/harmonization");

    expect(await screen.findByText(/no observations to harmonize/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /re-run associations/i })).toBeDisabled();
  });

  it("shows normalization, association and event results", async () => {
    installFetchMock({ summary: FIXTURE_SUMMARY, matches: MATCHES, events: EVENTS });
    renderApp("/harmonization");

    expect(await screen.findByText(/demo data only/i)).toBeInTheDocument();

    // Summary tiles reconcile with the API payload.
    expect(await screen.findByText(/1 probable/)).toBeInTheDocument();
    expect(screen.getByText(/2 seen by both sensors/i)).toBeInTheDocument();

    // Match table lists a cross-sensor pair and its score.
    expect((await screen.findAllByText("0.912")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("MODIS").length).toBeGreaterThan(0);
    expect(screen.getAllByText("VIIRS").length).toBeGreaterThan(0);
  });

  it("shows the evidence behind the selected match", async () => {
    installFetchMock({ summary: FIXTURE_SUMMARY, matches: MATCHES, events: EVENTS });
    renderApp("/harmonization");

    expect(await screen.findByText(/temporal similarity/i)).toBeInTheDocument();
    expect(screen.getByText(/geographic proximity/i)).toBeInTheDocument();
    expect(screen.getByText(/footprint overlap/i)).toBeInTheDocument();
    expect(screen.getByText(/not the probability that both detections/i)).toBeInTheDocument();
  });

  it("labels estimated events as estimates, not confirmed fires", async () => {
    installFetchMock({ summary: FIXTURE_SUMMARY, matches: MATCHES, events: EVENTS });
    renderApp("/harmonization");

    await waitFor(() => {
      expect(screen.getByText(/estimated fire events/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/not a confirmed fire/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/12\.4 MW/)).length).toBeGreaterThan(0);
  });

  it("states the analysis scope of the last association run", async () => {
    installFetchMock({ summary: FIXTURE_SUMMARY, matches: MATCHES, events: EVENTS });
    renderApp("/harmonization");

    expect(await screen.findByText(/bbox 2\.5, 4, 14\.7, 13\.9/)).toBeInTheDocument();
    expect((await screen.findAllByText(/2026-10-29/)).length).toBeGreaterThan(0);
  });
});
