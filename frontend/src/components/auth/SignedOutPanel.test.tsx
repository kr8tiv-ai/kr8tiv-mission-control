import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SignedOutPanel } from "./SignedOutPanel";

vi.mock("@/auth/clerk", () => ({
  SignInButton: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

describe("SignedOutPanel", () => {
  it("always exposes a local token login fallback link", () => {
    render(
      <SignedOutPanel
        message="Sign in to view boards."
        forceRedirectUrl="/boards"
      />,
    );

    expect(
      screen.getByRole("link", { name: /login with access token/i }),
    ).toHaveAttribute("href", "/local-login");
  });
});
