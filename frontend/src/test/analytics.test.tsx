import { beforeEach, describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";
import { trendBars } from "@/lib/analyticsApi";
import type { AnalyticsResponse, AnomaliesResponse } from "@/lib/analyticsApi";

const ANALYTICS: AnalyticsResponse = {
  start_date: "2026-10-29",
  end_date: "2026-10-31",
  totals: {
    detections: 133237,
    modis: 483,
    viirs: 132754,
    frp_sum_mw: 1098304.31,
    frp_max_mw: 675.5,
    high_confidence: 6647,
    active_days: 3,
    days: 7,
    mean_daily_detections: 19033.9,
  },
  series: [
    { date: "2026-10-28", detections: 0, modis: 0, viirs: 0, frp_sum_mw: 0 },
    { date: "2026-10-29", detections: 55612, modis: 177, viirs: 55435, frp_sum_mw: 456406.78 },
    { date: "2026-10-30", detections: 39377, modis: 306, viirs: 39071, frp_sum_mw: 310845.12 },
    { date: "2026-10-31", detections: 38248, modis: 0, viirs: 38248, frp_sum_mw: 331052.41 },
  ],
  top_cells: [
    { latitude: -2, longitude: 27, detections: 4021, frp_sum_mw: 30211.5, frp_max_mw: 210.8 },
    { latitude: 10, longitude: 30, detections: 3880, frp_sum_mw: 28110.2, frp_max_mw: 180.4 },
  ],
  cell_degrees: 2,
  peaks: {
    detections: { date: "2026-10-29", detections: 55612 },
    frp: { date: "2026-10-29", frp_mw: 675.5 },
  },
  confidence: { high: 6647, nominal: 110552, low: 16038, unknown: 0 },
  daynight: { D: 101932, N: 31305, unknown: 0 },
  satellites: [
    { satellite: "Suomi-NPP", detections: 132754, frp_sum_mw: 1082987.4 },
    { satellite: "Terra", detections: 483, frp_sum_mw: 15316.9 },
  ],
  products: [
    { source_code: "VIIRS_SNPP_NRT", detections: 132754 },
    { source_code: "MODIS_NRT", detections: 483 },
  ],
  synthetic_detections: 0,
  notes: ["Counts are thermal detections, not fires."],
};

const ANOMALIES_OK: AnomaliesResponse = {
  status: "ok",
  method: {
    name: "robust_z",
    version: "anomaly-robust-z-v1",
    baseline_days: 30,
    min_baseline_days: 14,
    z_threshold: 3,
    metric: "detections",
    mad_to_sigma: 1.4826,
    comparison: "preceding observed days, gaps excluded",
  },
  baseline: { days: 30, median: 6, mad: 1, scale: 1.48 },
  points: [],
  anomalies: [
    {
      date: "2026-11-05",
      observed: 412,
      expected: 6,
      deviation: 406,
      robust_z: 274.3,
      severity: "critical",
      explanation:
        "2026-11-05: 412 detections against a baseline median of 6.0 over the preceding 30 observed days (68.7× the median); robust z = 274.30.",
    },
  ],
  evaluated_days: 1,
  observed_baseline_days: 30,
  requirements: { needed_days: 14, available_days: 30, note: "Requirement satisfied." },
  notes: ["Counts are detections, not fires."],
};

beforeEach(() => {
  installFetchMock({ analytics: ANALYTICS });
});

describe("analytics helpers", () => {
  it("normalises the trend to the busiest day", () => {
    const bars = trendBars(ANALYTICS.series);
    expect(bars[0]!.ratio).toBe(0);
    expect(bars[1]!.ratio).toBe(1);
    expect(bars[2]!.ratio).toBeCloseTo(39377 / 55612, 5);
  });

  it("keeps an all-zero series flat instead of dividing by zero", () => {
    const bars = trendBars([
      { date: "2026-10-01", detections: 0, modis: 0, viirs: 0, frp_sum_mw: 0 },
    ]);
    expect(bars[0]!.ratio).toBe(0);
  });
});

describe("analytics page", () => {
  it("renders totals, breakdowns and the ranked cells", async () => {
    renderApp("/analytics");

    expect(await screen.findByRole("heading", { name: /analytics/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("133,237").length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/3 \/ 7/)).toBeInTheDocument();
    expect(screen.getByText(/top activity cells/i)).toBeInTheDocument();
    expect(screen.getByText(/4,021/)).toBeInTheDocument();
    expect(screen.getByText(/Suomi-NPP/)).toBeInTheDocument();
    // Rankings are cells, not countries.
    expect(screen.getByText(/cells, not countries/i)).toBeInTheDocument();
  });
});

describe("anomaly page", () => {
  it("refuses to score without enough history", async () => {
    renderApp("/anomalies");

    expect(
      await screen.findByText(/not enough history for a baseline/i),
    ).toBeInTheDocument();
    // The sentence is split by emphasis spans, so assert on the rendered text.
    const text = document.body.textContent ?? "";
    expect(text).toContain("0 observed baseline days are available");
    expect(text).toContain("14 are required");
  });

  it("shows flagged days with their explanation once a baseline exists", async () => {
    installFetchMock({ anomalies: ANOMALIES_OK });
    renderApp("/anomalies");

    expect(await screen.findByText("2026-11-05")).toBeInTheDocument();
    expect(screen.getByText(/critical/i)).toBeInTheDocument();
    expect(screen.getByText(/68\.7× the median/)).toBeInTheDocument();
  });
});
