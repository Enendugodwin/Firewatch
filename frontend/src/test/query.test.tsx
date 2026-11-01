import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";
import type { Observation } from "@/types/api";
import type { CalendarResponse } from "@/lib/calendarApi";

const OBSERVATION: Observation = {
  id: "obs-query-1",
  source_code: "VIIRS_SNPP_NRT",
  source_record_id: "q-1",
  sensor: "VIIRS",
  satellite: "Suomi-NPP",
  latitude: 9.0612,
  longitude: 7.4951,
  acquired_at: "2026-10-30T12:41:00Z",
  confidence_raw: null,
  confidence_category: "nominal",
  brightness_temperature: 331.2,
  brightness_channel: "viirs_bright_ti4_4um",
  frp_mw: 8.42,
  scan_km: 0.375,
  track_km: 0.375,
  daynight: "D",
  processing_version: "2.0NRT",
  source_product: "VIIRS_SNPP_NRT",
  quality_flags: { normalizer: "normalize-v1" },
  is_synthetic: false,
};

const SUMMARY: CalendarResponse = {
  granularity: "day",
  start_date: "2026-10-29",
  end_date: "2026-10-31",
  buckets: [],
  totals: {
    detections: 1,
    modis: 0,
    viirs: 1,
    frp_sum_mw: 8.42,
    frp_max_mw: 8.42,
    high_confidence: 0,
    active_buckets: 1,
    quiet_buckets: 0,
    unobserved_buckets: 0,
    buckets: 1,
  },
  notes: [],
};

let fetchMock: ReturnType<typeof installFetchMock>;

beforeEach(() => {
  fetchMock = installFetchMock({
    query: { observations: { items: [OBSERVATION], total: 1, limit: 200, offset: 0 } },
    calendar: {
      calendar: SUMMARY,
      drilldown: {
        bucket: {
          start: "2026-10-30",
          end: "2026-10-30",
          label: "2026-10-30",
          state: "active",
          coverage: { observed: 1, empty: 0, missing: 0, unknown: 0 },
          detections: 1,
          modis: 0,
          viirs: 1,
          frp_sum_mw: 8.42,
          frp_max_mw: 8.42,
          high_confidence: 0,
        },
        total: 1,
        returned: 1,
        limit: 200,
        items: [OBSERVATION],
      },
    },
  });
});

function requestedUrls() {
  return fetchMock.mock.calls.map((call) => String(call[0]));
}

describe("data query page", () => {
  it("is reachable under the Intelligence navigation", async () => {
    renderApp("/query");

    expect(await screen.findByRole("heading", { name: /data query/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /data query/i })).toHaveAttribute("href", "/query");
  });

  it("lists matching detections with their provenance on click", async () => {
    renderApp("/query");

    const row = await screen.findByText(/2026-10-30 12:41Z/);
    fireEvent.click(row);

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText(/q-1/)).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("applies a query so only the requested data is returned", async () => {
    renderApp("/query");
    await screen.findByText(/2026-10-30 12:41Z/);

    fireEvent.change(screen.getByLabelText(/^sensor$/i), { target: { value: "VIIRS" } });
    fireEvent.click(screen.getByRole("button", { name: /apply query/i }));

    await waitFor(() => {
      const urls = requestedUrls();
      expect(
        urls.some((url) => url.includes("/api/v1/fires?") && url.includes("sensor=VIIRS")),
      ).toBe(true);
      expect(
        urls.some((url) => url.includes("/api/v1/calendar?") && url.includes("sensor=VIIRS")),
      ).toBe(true);
    });
  });

  it("searches by an exact time and date range", async () => {
    renderApp("/query");
    await screen.findByText(/2026-10-30 12:41Z/);

    fireEvent.change(screen.getByLabelText(/^from \(utc\)$/i), {
      target: { value: "2026-10-30T06:00" },
    });
    fireEvent.change(screen.getByLabelText(/^to \(utc\)$/i), {
      target: { value: "2026-10-30T18:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: /apply query/i }));

    await waitFor(() => {
      const urls = requestedUrls();
      expect(
        urls.some(
          (url) =>
            url.includes("/api/v1/fires?") &&
            url.includes("start_at=2026-10-30T06%3A00%3A00Z") &&
            url.includes("end_at=2026-10-30T18%3A00%3A00Z"),
        ),
      ).toBe(true);
    });
  });

  it("applies a preset window", async () => {
    renderApp("/query");
    await screen.findByText(/2026-10-30 12:41Z/);

    fireEvent.click(screen.getByRole("button", { name: /last 24 h/i }));
    fireEvent.click(screen.getByRole("button", { name: /apply query/i }));

    await waitFor(() => {
      expect(requestedUrls().some((url) => url.includes("start_at="))).toBe(true);
    });
  });

  it("exports the matching detections with the current scope", async () => {
    renderApp("/query");
    await screen.findByText(/2026-10-30 12:41Z/);

    fireEvent.change(screen.getByLabelText(/^sensor$/i), { target: { value: "VIIRS" } });
    fireEvent.click(screen.getByRole("button", { name: /apply query/i }));

    await waitFor(() => {
      const link = screen.getByRole("link", { name: /export csv/i });
      const href = link.getAttribute("href") ?? "";
      expect(href).toContain("/api/v1/fires/export.csv?");
      expect(href).toContain("sensor=VIIRS");
      expect(link).toHaveAttribute("download");
    });
  });

  it("constrains the query to a searched region", async () => {
    renderApp("/query");
    await screen.findByText(/2026-10-30 12:41Z/);

    const input = screen.getByLabelText(/search a region/i);
    fireEvent.change(input, { target: { value: "Nigeria" } });
    const option = await screen.findByRole("button", { name: /nigeria/i });
    fireEvent.click(option);
    fireEvent.click(screen.getByRole("button", { name: /apply query/i }));

    await waitFor(() => {
      expect(requestedUrls().some((url) => url.includes("bbox="))).toBe(true);
    });
  });
});
