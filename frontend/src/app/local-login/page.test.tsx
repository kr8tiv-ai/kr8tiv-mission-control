import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import LocalLoginPage from "./page";

const localAuthLoginPropsSpy = vi.fn();

vi.mock("@/components/organisms/LocalAuthLogin", () => ({
  LocalAuthLogin: (props: unknown) => {
    localAuthLoginPropsSpy(props);
    return <div data-testid="local-auth-login" />;
  },
}));

describe("/local-login routing contract", () => {
  it("passes an authenticated redirect callback to LocalAuthLogin", () => {
    render(<LocalLoginPage />);

    expect(screen.getByTestId("local-auth-login")).toBeInTheDocument();
    expect(localAuthLoginPropsSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        onAuthenticated: expect.any(Function),
      }),
    );
  });
});
