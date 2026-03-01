"use client";

import { useSearchParams } from "next/navigation";
import { SignIn } from "@clerk/nextjs";

import { isClerkEnabled } from "@/auth/clerk";
import { resolveSignInRedirectUrl } from "@/auth/redirects";
import { LocalAuthLogin } from "@/components/organisms/LocalAuthLogin";

export default function SignInPage() {
  const searchParams = useSearchParams();
  const forceRedirectUrl = resolveSignInRedirectUrl(
    searchParams.get("redirect_url"),
  );

  if (!isClerkEnabled()) {
    return <LocalAuthLogin onAuthenticated={() => window.location.replace("/boards")} />;
  }

  // Dedicated sign-in route for Cypress E2E.
  // Avoids modal/iframe auth flows and gives Cypress a stable top-level page.
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <SignIn
        routing="path"
        path="/sign-in"
        forceRedirectUrl={forceRedirectUrl}
      />
    </main>
  );
}
