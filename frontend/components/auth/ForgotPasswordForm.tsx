"use client";

import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { forgotPasswordSchema } from "@/lib/validation/auth";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useState } from "react";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
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
                : "Unable to send reset email.",
            ),
          )
          .finally(() => setPending(false));
      }}
    >
      {sent ? (
        <Alert variant="success" title="Check your inbox">
          If an account exists for {email}, a reset link has been sent.
        </Alert>
      ) : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Input
        label="Email"
        name="email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <Button type="submit" className="w-full" disabled={pending}>
        {pending ? "Sending…" : "Send reset link"}
      </Button>
      <p className="text-center text-sm">
        <Link href={ROUTES.login} className="text-secondary hover:underline">
          Back to sign in
        </Link>
      </p>
    </form>
  );
}
