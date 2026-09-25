"use client";

import {
  AuthCheckbox,
  AuthField,
  AuthSubmitButton,
} from "@/components/auth/AuthField";
import { Alert } from "@/components/ui/Alert";
import { useLoginForm } from "@/features/auth/useLoginForm";
import { useLiveFields } from "@/lib/validation/live";
import { loginSchema } from "@/lib/validation/auth";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

export function LoginForm() {
  const { submit, errors: submitErrors, formError, pending } = useLoginForm();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const live = useLiveFields(loginSchema, { email, password });
  const errors = { ...submitErrors, ...live.errors };

  useEffect(() => {
    const prefill = searchParams.get("email");
    if (prefill) setEmail(prefill);
  }, [searchParams]);

  const registerHref = useMemo(() => {
    const next = searchParams.get("next");
    const params = new URLSearchParams();
    if (next?.startsWith("/") && !next.startsWith("//")) {
      params.set("next", next);
      try {
        const nextUrl = new URL(next, "http://local");
        const invite = nextUrl.searchParams.get("token");
        if (invite && nextUrl.pathname === ROUTES.acceptInvitation) {
          params.set("invite", invite);
        }
      } catch {
        
      }
    }
    if (email) params.set("email", email);
    const qs = params.toString();
    return qs ? `${ROUTES.register}?${qs}` : ROUTES.register;
  }, [email, searchParams]);

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        void remember;
        if (!live.finish()) return;
        void submit({ email, password });
      }}
    >
      <div>
        <p className="auth-kicker">Sign in</p>
        <h1 className="auth-display mt-2 text-[2.05rem] sm:text-[2.45rem]">
          Welcome back
        </h1>
        <p className="auth-lede mt-2.5">
          Sign in with your company email to enter your organization on TradeBay.
        </p>
      </div>

      {formError ? <Alert variant="error">{formError}</Alert> : null}

      <AuthField
        label="Company email"
        name="email"
        type="email"
        icon="mail"
        autoComplete="email"
        placeholder="you@company.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        onBlur={() => live.touch("email")}
        error={errors.email}
      />

      <AuthField
        label="Password"
        name="password"
        type="password"
        icon="lock"
        autoComplete="current-password"
        placeholder="••••••••"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onBlur={() => live.touch("password")}
        error={errors.password}
      />

      <div className="flex items-center justify-between gap-3">
        <AuthCheckbox
          id="remember"
          label="Remember me"
          checked={remember}
          onChange={setRemember}
        />
        <Link
          href={ROUTES.forgotPassword}
          className="text-sm font-semibold text-link transition hover:text-heading"
        >
          Forgot password?
        </Link>
      </div>

      <AuthSubmitButton pending={pending} tone="green">
        {pending ? "Signing in…" : "Sign in"}
      </AuthSubmitButton>

      <p className="pt-1 text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{" "}
        <Link
          href={registerHref}
          className="font-semibold text-heading hover:underline"
        >
          Create one
        </Link>
      </p>
    </form>
  );
}
