"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Lock } from "lucide-react";

import { getLocalAuthToken, isLocalAuthMode, setLocalAuthToken } from "@/auth/localAuth";
import { resolveSignInRedirectUrl } from "@/auth/redirects";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type LoginResult = {
  accessToken: string | null;
  error: string | null;
};

async function loginLocal(
  username: string,
  password: string,
): Promise<LoginResult> {
  const rawBaseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!rawBaseUrl) {
    return { accessToken: null, error: "NEXT_PUBLIC_API_URL is not set." };
  }

  const baseUrl = rawBaseUrl.replace(/\/+$/, "");

  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    return {
      accessToken: null,
      error: "Unable to reach Mission Control backend.",
    };
  }

  const payload = (await response.json().catch(() => null)) as
    | { access_token?: unknown; detail?: unknown }
    | null;

  if (response.ok) {
    const accessToken =
      payload && typeof payload.access_token === "string"
        ? payload.access_token
        : null;
    if (!accessToken) {
      return {
        accessToken: null,
        error: "Mission Control login returned an invalid response.",
      };
    }
    return { accessToken, error: null };
  }

  if (typeof payload?.detail === "string" && payload.detail) {
    return { accessToken: null, error: payload.detail };
  }

  if (response.status === 401 || response.status === 403) {
    return {
      accessToken: null,
      error: "Invalid Mission Control username or password.",
    };
  }

  return {
    accessToken: null,
    error: `Unable to sign in (HTTP ${response.status}).`,
  };
}

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectUrl = resolveSignInRedirectUrl(searchParams.get("redirect_url"));
  const localMode = isLocalAuthMode();
  const [username, setUsername] = useState("matt");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!localMode) {
      router.replace(`/sign-in?redirect_url=${encodeURIComponent(redirectUrl)}`);
      return;
    }
    if (getLocalAuthToken()) {
      router.replace(redirectUrl);
    }
  }, [localMode, redirectUrl, router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanedUsername = username.trim();
    if (!cleanedUsername) {
      setError("Username is required.");
      return;
    }
    if (!password) {
      setError("Password is required.");
      return;
    }

    setIsSubmitting(true);
    const result = await loginLocal(cleanedUsername, password);
    setIsSubmitting(false);
    if (result.error || !result.accessToken) {
      setError(result.error ?? "Mission Control login failed.");
      return;
    }

    setLocalAuthToken(result.accessToken);
    setError(null);
    router.replace(redirectUrl);
    router.refresh();
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#050505] px-4 py-10 text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(44,255,213,0.16),transparent_32%),radial-gradient(circle_at_bottom_right,rgba(79,70,229,0.18),transparent_28%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(45deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:34px_34px] opacity-40" />
      <div className="pointer-events-none absolute left-8 top-8 border border-white/10 bg-black/70 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.28em] text-[#2cffd5]">
        KR8TIV // Friday Control
      </div>

      <Card className="relative w-full max-w-lg rounded-none border border-white/10 bg-black/90 shadow-[0_0_0_1px_rgba(44,255,213,0.08),0_30px_120px_rgba(0,0,0,0.55)]">
        <CardHeader className="space-y-6 border-b border-white/10 pb-6">
          <div className="flex items-center justify-between">
            <span className="border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-zinc-300">
              Mission Control Login
            </span>
            <div className="border border-[#2cffd5]/40 bg-[#2cffd5]/10 p-2 text-[#2cffd5]">
              <Lock className="h-5 w-5" />
            </div>
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold uppercase tracking-[0.08em] text-white">
              Friday access
            </h1>
            <p className="max-w-md text-sm leading-6 text-zinc-400">
              Enter the admin credentials to unlock the Friday operations dashboard, Supermemory feed, and Telegram-linked control surface.
            </p>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label
                htmlFor="mission-control-username"
                className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-400"
              >
                Username
              </label>
              <Input
                id="mission-control-username"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="matt"
                autoFocus
                disabled={isSubmitting}
                className="rounded-none border-white/10 bg-white/[0.04] text-white placeholder:text-zinc-600"
              />
            </div>
            <div className="space-y-2">
              <label
                htmlFor="mission-control-password"
                className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-400"
              >
                Password
              </label>
              <Input
                id="mission-control-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter admin password"
                disabled={isSubmitting}
                className="rounded-none border-white/10 bg-white/[0.04] font-mono text-white placeholder:text-zinc-600"
              />
            </div>
            {error ? (
              <p className="border border-red-500/30 bg-red-500/10 px-3 py-3 text-sm text-red-200">
                {error}
              </p>
            ) : (
              <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">
                Friday is the only active agent in this environment.
              </p>
            )}
            <Button
              type="submit"
              className="w-full rounded-none bg-[#2cffd5] text-black hover:bg-[#7dffea]"
              size="lg"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Authorizing…" : "Enter Mission Control"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
