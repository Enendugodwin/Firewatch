import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock, makeStatus } from "@/test/fixtures";

let fetchMock: ReturnType<typeof installFetchMock>;

beforeEach(() => {
  // A configured key is what enables the buttons under test.
  fetchMock = installFetchMock({ status: makeStatus({ firms_configured: true }) });
});

function callsTo(fragment: string) {
  return fetchMock.mock.calls.filter((call) => String(call[0]).includes(fragment));
}

describe("ingestion console", () => {
  it("offers a single action that ingests every source", async () => {
    renderApp("/settings");

    const button = await screen.findByRole("button", { name: /run all sources/i });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);

    await waitFor(() => {
      const posts = fetchMock.mock.calls.filter(
        (call) => String(call[0]).includes("/admin/ingestion/run-all"),
      );
      expect(posts.length).toBe(1);
    });

    expect(await screen.findByText(/2 of 2 sources ingested/i)).toBeInTheDocument();
    expect(screen.getByText(/MODIS_NRT/)).toBeInTheDocument();
    expect(screen.getByText(/VIIRS_SNPP_NRT/)).toBeInTheDocument();
  });

  it("refreshes every derived view after ingestion", async () => {
    renderApp("/settings");

    const before = callsTo("/api/v1/system/sources").length;
    const button = await screen.findByRole("button", { name: /run all sources/i });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);

    await waitFor(() => {
      // Ingestion invalidates the whole cache, so the source registry refetches.
      expect(callsTo("/api/v1/system/sources").length).toBeGreaterThan(before);
    });
  });
});

describe("match export", () => {
  it("links the CSV export to the current filter", async () => {
    renderApp("/harmonization");

    const link = await screen.findByRole("link", { name: /export csv/i });
    expect(link).toHaveAttribute("href", "/api/v1/harmonization/matches.csv");
    expect(link).toHaveAttribute("download");
  });
});
