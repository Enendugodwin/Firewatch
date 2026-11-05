import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import { renderApp } from "@/test/render";
import { installFetchMock } from "@/test/fixtures";

describe("operator sign-in", () => {
  it("signs in and lands on the admin portal", async () => {
    installFetchMock();
    renderApp("/login");

    fireEvent.change(await screen.findByLabelText(/email/i), {
      target: { value: "ops@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "correct-horse-battery" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(
      await screen.findByRole("heading", { name: /admin portal/i }),
    ).toBeInTheDocument();
  });
});
