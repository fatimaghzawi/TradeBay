"use client";

import { AuthField, AuthSubmitButton } from "@/components/auth/AuthField";
import { ResetStepper } from "@/components/auth/ResetPasswordForm";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { forgotPasswordSchema } from "@/lib/validation/auth";
import { useLiveFields } from "@/lib/validation/live";
import { BackLink } from "@/components/ui/BackLink";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useState } from "react";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);
  const live = useLiveFields(forgotPasswordSchema, { email });

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        if (!live.finish()) return;
        const parsed = forgotPasswordSchema.safeParse({ email });
        if (!parsed.success) {
          setError(parsed.error.issues[0]?.message ?? "Invalid email");
          return;
        }
        setPending(true);
        void authApi
          .forgotPassword(parsed.data.email)
          .then(() => setSent(true))
          .catch((err) =>
            setError(
              err instanceof ApiError
                ? err.message
                : "Couldn't send reset email.",
            ),
          )
          .finally(() => setPending(false));
      }}
    >
      <ResetStepper active="request" />

      <div>
        <h1 className="auth-display text-[1.95rem] sm:text-[2.25rem]">
          Forgot password?
        </h1>
        <p className="auth-lede mt-2">
          Enter your email and we&apos;ll send a 6-digit reset code if an account
          exists.
        </p>
      </div>

      {sent ? (
        <div className="rounded-xl bg-secondary-soft px-3.5 py-3 text-sm text-heading ring-1 ring-border">
          <p className="font-semibold text-link">Check your inbox</p>
          <p className="mt-1 text-muted-foreground">
            If an account exists for{" "}
            <span className="font-semibold text-heading">{email}</span>, a 6-digit reset code
            has been sent. Enter it on the next screen to set your new password.
          </p>
          <Link
            href={`${ROUTES.resetPassword}?email=${encodeURIComponent(email)}`}
            className="mt-3 inline-flex font-semibold text-link underline-offset-2 hover:underline"
          >
            Enter reset code →
          </Link>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="tb-alert tb-alert--error">
          {error}
        </p>
      ) : null}

      {!sent ? (
        <>
          <AuthField
            label="Email address"
            name="email"
            type="email"
            icon="mail"
            placeholder="you@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={() => live.touch("email")}
            error={live.errors.email}
          />

          <AuthSubmitButton pending={pending} tone="orange">
            {pending ? "Sending…" : "Send reset code"}
          </AuthSubmitButton>
        </>
      ) : null}

      <p className="flex justify-center">
        <BackLink href={ROUTES.login}>Back to sign in</BackLink>
      </p>
    </form>
  );
}
