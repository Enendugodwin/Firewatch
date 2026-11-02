import { describe, expect, it, beforeEach } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";

beforeEach(() => {
  installFetchMock();
});

describe("regional intelligence page", () => {
  it("shows the materialised regional statistics, not a fabricated zero", async () => {
    renderApp("/regions");

    expect(
      await screen.findByRole("heading", { name: /regional intelligence/i }),
    ).toBeInTheDocument();

    // Overview totals come from the stored regional statistics.
    expect(await screen.findByText("68,642")).toBeInTheDocument();

    // The headline: this month against the historical median.
    expect(screen.getByText(/median 3,000/)).toBeInTheDocument();
    expect(screen.getByText("+36.7%")).toBeInTheDocument();

    // Seasonality refuses a climatology from one year.
    expect(await screen.findByText(/^single year$/i)).toBeInTheDocument();
    expect(screen.getByText(/this is not a climatology/i)).toBeInTheDocument();

    // The trend card states why it withholds significance.
    expect(screen.getAllByText(/insufficient years/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/needs 8 complete years/i)).toBeInTheDocument();

    // Sensors are shown separately with a correlation, not a merged level.
    expect(await screen.findByText("65,568")).toBeInTheDocument();
    expect(screen.getByText(/r = 0.95/)).toBeInTheDocument();

    // The recurring-activity grid is labelled as a screening grid.
    expect(await screen.findByText(/8.75, 9.25/)).toBeInTheDocument();
    expect(screen.getByText(/screening grid/i)).toBeInTheDocument();
  });

  it("runs an analysis for the selected region and period", async () => {
    const fetchMock = installFetchMock();
    renderApp("/regions");

    // Wait until the catalogue has resolved and the button is enabled.
    await screen.findByRole("option", { name: /nigeria/i });
    const button = await screen.findByRole("button", { name: /analyse period/i });
    await waitFor(() => expect(button).not.toBeDisabled());
    fireEvent.click(button);

    await waitFor(() => {
      const posts = fetchMock.mock.calls.filter(
        (call) =>
          String(call[0]).includes("/api/v1/regions/") &&
          String(call[0]).includes("/analyze") &&
          (call[1] as RequestInit | undefined)?.method === "POST",
      );
      expect(posts.length).toBe(1);
    });
  });

  it("keeps the approximate ranking and links it to the engine", async () => {
    renderApp("/regions");

    expect((await screen.findAllByText("Nigeria")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/approximate centroid boxes/i).length).toBeGreaterThan(0);
    expect(await screen.findByRole("button", { name: /^open$/i })).toBeInTheDocument();
  });
});
