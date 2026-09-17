"use client";

import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

function VerifyEmailForm() {
  const params = useSearchParams();
  const [token, setToken] = useState(params.get("token") ?? "");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);
  const [resent, setResent] = useState(false);

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        setPending(true);
        void authApi
          .verifyEmail(token)
          .then(() => setDone(true))
          .catch((err) =>
            setError(err instanceof ApiError ? err.message : "Verification failed."),
          )
          .finally(() => setPending(false));
      }}
    >
      {done ? (
        <Alert variant="success" title="Email verified">
          You can now perform commercial actions on TradeBay.
        </Alert>
      ) : null}
      {resent ? <Alert variant="success">A new verification token was sent if your email is still unverified.</Alert> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Input
        label="Verification token"
        name="token"
        value={token}
        onChange={(e) => setToken(e.target.value)}
      />
      <Button type="submit" className="w-full" disabled={pending || !token}>
        {pending ? "Verifying…" : "Verify email"}
      </Button>
      <Button
        type="button"
        variant="outline"
        className="w-full"
        onClick={() => {
          setError(null);
          void authApi
            .resendVerification()
            .then(() => setResent(true))
            .catch((err) =>
              setError(err instanceof ApiError ? err.message : "Unable to resend. Sign in first."),
            );
        }}
      >
        Resend verification
      </Button>
      <p className="text-center text-sm">
        <Link href={ROUTES.login} className="text-secondary hover:underline">
          Back to sign in
        </Link>
      </p>
    </form>
  );
}

export default function VerifyEmailPage() {
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold text-primary">Verify email</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Enter the one-time token from your email. Commercial writes stay blocked until this succeeds.
      </p>
      <div className="mt-6">
        <Suspense>
          <VerifyEmailForm />
        </Suspense>
      </div>
    </div>
  );
}
