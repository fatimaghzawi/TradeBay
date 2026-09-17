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

function ResetPasswordForm() {
  const params = useSearchParams();
  const [token, setToken] = useState(params.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        setPending(true);
        void authApi
          .resetPassword(token, password)
          .then(() => setDone(true))
          .catch((err) =>
            setError(err instanceof ApiError ? err.message : "Reset failed."),
          )
          .finally(() => setPending(false));
      }}
    >
      {done ? (
        <Alert variant="success" title="Password updated">
          Sign in with your new password. Previous sessions were revoked.
        </Alert>
      ) : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Input
        label="Reset token"
        name="token"
        value={token}
        onChange={(e) => setToken(e.target.value)}
      />
      <Input
        label="New password"
        name="password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button type="submit" className="w-full" disabled={pending || !token || password.length < 8}>
        {pending ? "Saving…" : "Set new password"}
      </Button>
      <p className="text-center text-sm">
        <Link href={ROUTES.login} className="text-secondary hover:underline">
          Back to sign in
        </Link>
      </p>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold text-primary">Choose a new password</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Use the one-time reset token. It expires and cannot be reused.
      </p>
      <div className="mt-6">
        <Suspense>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </div>
  );
}
