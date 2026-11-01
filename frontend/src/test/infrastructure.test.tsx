import { beforeEach, describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";
import { formatBytes } from "@/lib/infrastructureApi";

beforeEach(() => {
  installFetchMock();
});

describe("cloud readiness helpers", () => {
  it("formats byte counts for humans", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(41_335_227)).toMatch(/MB$/);
    expect(formatBytes(null)).toBe("—");
  });
});

describe("cloud readiness page", () => {
  it("shows the mode, storage and the dataset inventory", async () => {
    renderApp("/infrastructure");

    expect(await screen.findByRole("heading", { name: /cloud readiness/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText(/local/).length).toBeGreaterThan(0);
    });
    expect(await screen.findByText("detections-2026-10")).toBeInTheDocument();
    expect(screen.getAllByText(/1,120,880/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /export parquet/i })).toBeInTheDocument();
    expect(screen.getAllByText(/no cloud credentials/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/verified by size and sha-256/i).length).toBeGreaterThan(0);
  });
});
