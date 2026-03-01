import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import SignInPage from "./page";

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: () => null,
  }),
}));

vi.mock("@clerk/nextjs", () => ({
  SignIn: () => {
    throw new Error("Clerk SignIn should not render when Clerk is disabled");
  },
}));

describe("/sign-in local fallback", () => {
  it("renders local auth login when Clerk is unavailable", () => {
    process.env.NEXT_PUBLIC_AUTH_MODE = "clerk";
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "placeholder";
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";

    render(<SignInPage />);

    expect(screen.getByText(/authorization portal/i)).toBeInTheDocument();
    expect(
      screen.getByText(/paste your local auth token/i),
    ).toBeInTheDocument();
  });
});
