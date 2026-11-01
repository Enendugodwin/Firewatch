import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";
import { LoadingBlock, LoadingCue } from "@/components/ui/LoadingCue";
import { buildSparkline, seasonBarHeight } from "@/components/calendar/CalendarIntelligence";
import type { SeasonMonth, TrendPoint } from "@/lib/calendarApi";

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

beforeEach(() => {
  installFetchMock();
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

  it("keeps insufficient months visibly small in the seasonal profile", () => {
    const insufficient: SeasonMonth = {
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
});
