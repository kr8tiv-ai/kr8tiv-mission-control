import Link from "next/link";

import { SignInButton } from "@/auth/clerk";

import { Button } from "@/components/ui/button";

type SignedOutPanelProps = {
  message: string;
  forceRedirectUrl: string;
  signUpForceRedirectUrl?: string;
  mode?: "modal" | "redirect";
  buttonLabel?: string;
  buttonTestId?: string;
};

export function SignedOutPanel({
  message,
  forceRedirectUrl,
  signUpForceRedirectUrl,
  mode = "modal",
  buttonLabel = "Sign in",
  buttonTestId,
}: SignedOutPanelProps) {
  return (
    <div className="col-span-2 flex min-h-[calc(100vh-64px)] items-center justify-center bg-slate-50 p-10 text-center">
      <div className="rounded-xl border border-slate-200 bg-white px-8 py-6 shadow-sm">
        <p className="text-sm text-slate-600">{message}</p>
        <SignInButton
          mode={mode}
          forceRedirectUrl={forceRedirectUrl}
          signUpForceRedirectUrl={signUpForceRedirectUrl}
        >
          <Button className="mt-4" data-testid={buttonTestId}>
            {buttonLabel}
          </Button>
        </SignInButton>
        <div className="mt-3">
          <Link
            href="/local-login"
            className="text-xs font-medium text-slate-500 underline underline-offset-2 hover:text-slate-700"
          >
            Login with access token
          </Link>
        </div>
      </div>
    </div>
  );
}
