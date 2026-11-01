import { describe, expect, it, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";
import { LoadingBlock, LoadingCue } from "@/components/ui/LoadingCue";
import { buildSparkline, seasonBarHeight } from "@/components/calendar/CalendarIntelligence";
import type {
  CalendarBucket,
  CalendarDrilldown,
  CalendarResponse,
  SeasonMonth,
  TrendPoint,
} from "@/lib/calendarApi";
import { isRankedSeverity, maxSeverityInRange } from "@/lib/severity";

function point(overrides: Partial<TrendPoint>): TrendPoint {
  return {
    date: "2026-10-01",
    value: 10,
    observed: true,
    trailing_mean: 10,
    severity: "normal",
    ...overrides,
  };
}

const DAYS = Array.from(
  { length: 12 },
  (_, index) => `2026-10-${String(18 + index).padStart(2, "0")}`,
);

function dayBucket(start: string): CalendarBucket {
  return {
    start,
    end: start,
    label: start,
    state: "active",
    coverage: { observed: 1, empty: 0, missing: 0, unknown: 0 },
    detections: 100,
    modis: 40,
    viirs: 60,
    frp_sum_mw: 10,
    frp_max_mw: 5,
    high_confidence: 10,
  };
}

const CALENDAR_FIXTURE: CalendarResponse = {
  granularity: "day",
  start_date: DAYS[0]!,
  end_date: DAYS[DAYS.length - 1]!,
  buckets: DAYS.map(dayBucket),
  totals: {
    detections: 1200,
    modis: 480,
    viirs: 720,
    frp_sum_mw: 120,
    frp_max_mw: 5,
    high_confidence: 120,
    active_buckets: 12,
    quiet_buckets: 0,
    unobserved_buckets: 0,
    buckets: 12,
  },
  notes: ["Each bucket counts thermal detections, not fires."],
};

const DRILLDOWN_FIXTURE: CalendarDrilldown = {
  bucket: dayBucket(DAYS[0]!),
  total: 0,
  returned: 0,
  limit: 200,
  items: [],
};

beforeEach(() => {
  installFetchMock({
    calendar: { calendar: CALENDAR_FIXTURE, drilldown: DRILLDOWN_FIXTURE },
  });
});

describe("calendar intelligence helpers", () => {
  it("breaks the sparkline at a gap instead of drawing it as zero", () => {
    const geometry = buildSparkline([
      point({ date: "2026-10-01", value: 10 }),
      point({ date: "2026-10-02", value: null, observed: false, trailing_mean: null, severity: "unobserved" }),
      point({ date: "2026-10-03", value: 20, severity: "high" }),
    ]);

    expect(geometry.linePaths).toHaveLength(2);
    expect(geometry.dots).toHaveLength(1);
    expect(geometry.dots[0]!.date).toBe("2026-10-03");
  });

  it("marks only ranked anomalies as dots", () => {
    const geometry = buildSparkline([
      point({ date: "2026-10-01", severity: "normal" }),
      point({ date: "2026-10-02", severity: "below_baseline" }),
      point({ date: "2026-10-03", severity: "critical" }),
    ]);

    expect(geometry.dots.map((dot) => dot.date)).toEqual(["2026-10-03"]);
  });

  it("reports the strongest anomaly in a multi-day bucket", () => {
    const map = {
      "2026-10-27": "moderate",
      "2026-10-29": "critical",
      "2026-10-30": "below_baseline",
    };

    expect(maxSeverityInRange(map, "2026-10-26", "2026-11-01")).toBe("critical");
    expect(maxSeverityInRange(map, "2026-10-27", "2026-10-27")).toBe("moderate");
    // A drop below baseline is informative, but it is not an alert marker.
    expect(maxSeverityInRange(map, "2026-10-30", "2026-10-30")).toBeNull();
    expect(maxSeverityInRange(undefined, "2026-10-26", "2026-11-01")).toBeNull();
    expect(isRankedSeverity("unobserved")).toBe(false);
    expect(isRankedSeverity("high")).toBe(true);
  });

  it("keeps insufficient months visibly small in the seasonal profile", () => {    const insufficient: SeasonMonth = {
      month: 1,
      label: "Jan",
      mean: null,
      years: 0,
      sufficient: false,
      index: null,
    };
    const sufficient: SeasonMonth = {
      month: 7,
      label: "Jul",
      mean: 120,
      years: 2,
      sufficient: true,
      index: 5,
    };

    expect(seasonBarHeight(insufficient, 10)).toBeLessThan(
      seasonBarHeight(sufficient, 10),
    );
    expect(seasonBarHeight(sufficient, 10)).toBe(50);
  });
});

describe("loading cues", () => {
  it("announces what is loading with a live status region", () => {
    render(<LoadingCue label="Computing trend, anomaly baseline and seasonal profile…" />);

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/computing trend/i);
    expect(status).toHaveAttribute("aria-live", "polite");
  });

  it("holds the panel's space with skeleton lines", () => {
    const { container } = render(<LoadingBlock label="Loading…" lines={3} />);
    const skeletons = container.querySelectorAll("[aria-hidden]");
    expect(skeletons.length).toBeGreaterThanOrEqual(3);
  });
});

describe("calendar intelligence panel", () => {
  it("shows a loading cue before the result arrives", () => {
    renderApp("/calendar");

    // The first render is synchronous with the queries still in flight.
    expect(screen.queryByText(/loading calendar buckets/i)).toBeInTheDocument();
  });

  it("renders trend, anomaly and seasonality sections with their caveats", async () => {
    renderApp("/calendar");

    expect(
      await screen.findByRole("heading", { name: /trends, anomalies & seasonality/i }),
    ).toBeInTheDocument();

    // Trend direction and the method that produced it.
    expect(await screen.findByText(/rising/i)).toBeInTheDocument();
    expect(screen.getAllByText(/theil–sen/i).length).toBeGreaterThan(0);

    // The anomaly is an actionable row, not just a dot on a chart.
    expect(
      screen.getByRole("button", { name: /2026-10-29.*vs expected/i }),
    ).toBeInTheDocument();

    // Seasonality refuses to claim a climatology from one year.
    expect(screen.getByText(/^single year$/i)).toBeInTheDocument();
    expect(screen.getByText(/not a seasonal climatology/i)).toBeInTheDocument();

    // The standing caveat survives into the panel.
    expect(screen.getAllByText(/counts are detections, not fires/i).length).toBeGreaterThan(0);
  });

  it("marks anomalous days in the calendar grid itself", async () => {
    renderApp("/calendar");

    // 2026-10-29 carries a `high` anomaly in the intelligence fixture.
    const anomalous = await screen.findByRole("button", {
      name: /^2026-10-29: .*anomaly high/i,
    });
    expect(anomalous).toBeInTheDocument();

    const normal = screen.getByRole("button", { name: /^2026-10-28: / });
    expect(normal).not.toHaveAccessibleName(/anomaly/i);
  });

  it("carries the anomaly into week and month bars", async () => {
    renderApp("/calendar");

    fireEvent.click(await screen.findByRole("button", { name: /^week$/i }));

    const bar = await screen.findByRole("button", { name: /2026-10-29.*anomaly high/i });
    expect(bar).toBeInTheDocument();
  });
});
