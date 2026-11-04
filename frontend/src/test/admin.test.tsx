import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";

describe("admin portal", () => {
  it("shows the FIRMS key state without ever revealing a key", async () => {
    installFetchMock();
    renderApp("/admin");

    expect(await screen.findByRole("heading", { name: /admin portal/i })).toBeInTheDocument();
    expect(await screen.findByText(/not configured/i)).toBeInTheDocument();
    expect(screen.getByText(/NASA FIRMS MAP_KEY/i)).toBeInTheDocument();
  });

  it("saves a key and reports only its fingerprint", async () => {
    installFetchMock();
    renderApp("/admin");

    const input = await screen.findByPlaceholderText(/paste your firms map_key/i);
    fireEvent.change(input, { target: { value: "abcdef0123456789abcdef0123456789" } });
    fireEvent.click(screen.getByRole("button", { name: /save key/i }));

    expect(await screen.findByText(/9f2c/)).toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("stores an admin token for this tab", async () => {
    installFetchMock();
    renderApp("/admin");

    const input = await screen.findByPlaceholderText(/paste the admin_token/i);
    fireEvent.change(input, { target: { value: "tab-token" } });
    fireEvent.click(screen.getByRole("button", { name: /save token/i }));

    expect(window.sessionStorage.getItem("firewatch-admin-token")).toBe("tab-token");
  });

  it("shows the raw inventory and its retention policy", async () => {
    installFetchMock();
    renderApp("/admin");

    expect(await screen.findByText(/6,218,624/)).toBeInTheDocument();
    expect(screen.getAllByText(/2026-08-06/).length).toBeGreaterThan(0);
    expect(screen.getByText(/2024-12-01/)).toBeInTheDocument();
    expect(screen.getAllByText(/past retention/i).length).toBeGreaterThan(0);
  });
});
