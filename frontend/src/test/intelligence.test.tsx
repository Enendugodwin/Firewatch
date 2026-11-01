import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";

beforeEach(() => {
  installFetchMock();
});

describe("reports", () => {
  it("renders the snapshot and links both exports", async () => {
    renderApp("/reports");

    expect(await screen.findByRole("heading", { name: /reports/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText(/420/).length).toBeGreaterThan(0);
    });

    const markdown = screen.getByRole("link", { name: /markdown/i });
    expect(markdown).toHaveAttribute("href", expect.stringContaining("format=markdown"));
    expect(markdown).toHaveAttribute("download");
    expect(screen.getByRole("link", { name: /json/i })).toHaveAttribute(
      "href",
      expect.stringContaining("format=json"),
    );
  });
});

describe("regional intelligence", () => {
  it("ranks regions and states the approximation", async () => {
    renderApp("/regions");

    expect((await screen.findAllByText("Nigeria")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/approximate centroid boxes/i).length).toBeGreaterThan(0);
  });
});

describe("exposure", () => {
  it("lists assets and their nearby detections", async () => {
    renderApp("/exposure");

    expect((await screen.findAllByText("Depot")).length).toBeGreaterThan(0);
    expect(await screen.findByText(/1.2 km/)).toBeInTheDocument();
    expect(screen.getAllByText(/not a risk score/i).length).toBeGreaterThan(0);
  });

  it("adds an asset", async () => {
    const fetchMock = installFetchMock();
    renderApp("/exposure");

    const name = await screen.findByLabelText(/asset name/i);
    fireEvent.change(name, { target: { value: "Substation" } });
    fireEvent.click(screen.getByRole("button", { name: /add asset/i }));

    await waitFor(() => {
      const posts = fetchMock.mock.calls.filter(
        (call) =>
          String(call[0]).includes("/api/v1/exposure/assets") &&
          (call[1] as RequestInit | undefined)?.method === "POST",
      );
      expect(posts.length).toBe(1);
    });
  });
});

describe("assistant", () => {
  it("answers with the deterministic method and intent", async () => {
    renderApp("/assistant");

    fireEvent.click(await screen.findByRole("button", { name: /how many detections/i }));

    await waitFor(() => {
      expect(screen.getByText(/420 detections between/i)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/deterministic/i).length).toBeGreaterThan(0);
  });
});
