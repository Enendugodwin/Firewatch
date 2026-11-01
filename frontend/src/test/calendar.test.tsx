import { describe, expect, it, beforeEach } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";
import { groupIntoMonths } from "@/components/calendar/CalendarHeat";
import { intensity, metricValue } from "@/lib/calendarApi";
import type { CalendarBucket, CalendarResponse } from "@/lib/calendarApi";
import type { Observation } from "@/types/api";

function bucket(overrides: Partial<CalendarBucket> = {}): CalendarBucket {
  return {
    start: "2026-10-29",
    end: "2026-10-29",
    label: "2026-10-29",
    state: "active",
    coverage: { observed: 1, empty: 0, missing: 0, unknown: 0 },
    detections: 12,
    modis: 5,
    viirs: 7,
    frp_sum_mw: 42.5,
    frp_max_mw: 18.2,
    high_confidence: 3,
    ...overrides,
  };
}

const OBSERVATION: Observation = {
  id: "obs-cal-1",
  source_code: "VIIRS_SNPP_NRT",
  source_record_id: "cal123",
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

const CALENDAR: CalendarResponse = {
  granularity: "day",
  start_date: "2026-10-29",
  end_date: "2026-10-31",
  buckets: [
    bucket({ start: "2026-10-29", end: "2026-10-29", detections: 12 }),
    bucket({
      start: "2026-10-30",
      end: "2026-10-30",
      detections: 0,
      modis: 0,
      viirs: 0,
      frp_sum_mw: 0,
      frp_max_mw: null,
      high_confidence: 0,
      state: "quiet",
      coverage: { observed: 1, empty: 1, missing: 0, unknown: 0 },
    }),
    bucket({
      start: "2026-10-31",
      end: "2026-10-31",
      detections: 0,
      modis: 0,
      viirs: 0,
      frp_sum_mw: 0,
      frp_max_mw: null,
      high_confidence: 0,
      state: "unobserved",
      coverage: { observed: 0, empty: 0, missing: 0, unknown: 1 },
    }),
  ],
  totals: {
    detections: 12,
    modis: 5,
    viirs: 7,
    frp_sum_mw: 42.5,
    frp_max_mw: 18.2,
    high_confidence: 3,
    active_buckets: 1,
    quiet_buckets: 1,
    unobserved_buckets: 1,
    buckets: 3,
  },
  notes: [
    "Each bucket counts thermal detections, not fires.",
    "quiet means a source observed that period with no detections; unobserved means no availability was recorded, so it is not zero.",
  ],
};

const DRILLDOWN = {
  bucket: CALENDAR.buckets[1]!,
  total: 1,
  returned: 1,
  limit: 200,
  items: [OBSERVATION],
};

beforeEach(() => {
  installFetchMock({ calendar: { calendar: CALENDAR, drilldown: DRILLDOWN } });
});

describe("calendar helpers", () => {
  it("groups day buckets into Monday-first weeks per month", () => {
    const groups = groupIntoMonths([
      bucket({ start: "2026-10-26" }),
      bucket({ start: "2026-10-27" }),
      bucket({ start: "2026-11-02" }),
    ]);

    expect(groups).toHaveLength(2);
    expect(groups[0]!.key).toBe("2026-10");
    // A wall-calendar grid is always whole weeks; short months are padded.
    expect(groups[0]!.weeks.length).toBeGreaterThanOrEqual(5);
    expect(groups[0]!.weeks[0]).toHaveLength(7);
    // 2026-10-26 is a Monday, 2026-10-27 a Tuesday.
    expect(groups[0]!.weeks[0]![0]?.start).toBe("2026-10-26");
    expect(groups[0]!.weeks[0]![1]?.start).toBe("2026-10-27");
    expect(groups[1]!.key).toBe("2026-11");
  });

  it("maps metrics and keeps zero readable", () => {
    const quiet = bucket({ detections: 0, frp_sum_mw: 0, high_confidence: 0 });
    expect(metricValue(quiet, "detections")).toBe(0);
    expect(metricValue(quiet, "frp")).toBe(0);
    expect(intensity(0, 100)).toBe(0);
    expect(intensity(50, 100)).toBeGreaterThan(0);
    expect(intensity(100, 100)).toBe(1);
  });
});

describe("burning calendar page", () => {
  it("renders totals and distinguishes quiet from unobserved", async () => {
    renderApp("/calendar");

    expect(await screen.findByRole("heading", { name: /burning calendar/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText(/12/).length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/periods without data/i)).toBeInTheDocument();
    expect(screen.getAllByText(/no data/i).length).toBeGreaterThan(0);
  });

  it("opens a bucket drill-down with its detections", async () => {
    renderApp("/calendar");

    // Cell labels are "YYYY-MM-DD: value metric, state"; the header date button
    // also contains the date, so match the cell's full label.
    const day = await screen.findByRole("button", { name: /^2026-10-29: / });
    fireEvent.click(day);

    expect(await screen.findByText(/bucket detail/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/12:41Z/)).toBeInTheDocument();
    });
    // The query panel also offers "Nominal or higher", so match loosely.
    expect(screen.getAllByText(/nominal/i).length).toBeGreaterThan(0);
  });

  it("opens the selected detection in a centred dialog, not inline", async () => {
    renderApp("/calendar");

    const day = await screen.findByRole("button", { name: /^2026-10-29: / });
    fireEvent.click(day);
    const row = await screen.findByRole("button", { name: /12:41Z/ });
    fireEvent.click(row);

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveClass("mx-auto");
    expect(screen.getByText(/record id/i)).toBeInTheDocument();
    expect(screen.getByText(/cal123/)).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("labels an observed but empty period as a real zero", async () => {
    renderApp("/calendar");

    const day = await screen.findByRole("button", { name: /^2026-10-30: / });
    fireEvent.click(day);

    await waitFor(() => {
      expect(screen.getByText(/real zero/i)).toBeInTheDocument();
    });
  });

  it("explains that unobserved periods are not zero", async () => {
    renderApp("/calendar");

    const day = await screen.findByRole("button", { name: /^2026-10-31: / });
    fireEvent.click(day);

    await waitFor(() => {
      expect(screen.getByText(/cannot be read as zero/i)).toBeInTheDocument();
    });
  });
});
