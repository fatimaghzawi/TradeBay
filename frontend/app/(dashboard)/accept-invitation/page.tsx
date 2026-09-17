"use client";

import { ApiError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identityApi";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

function AcceptInvitationForm() {
  const params = useSearchParams();
  const { refreshSession } = useAuth();
  const [token, setToken] = useState(params.get("token") ?? "");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  return (
    <form
      className="max-w-md space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        void identityApi
          .acceptInvitation(token)
          .then(() => {
            setDone(true);
            void refreshSession();
          })
          .catch((err) =>
            setError(err instanceof ApiError ? err.message : "Invitation could not be accepted."),
          );
      }}
    >
      {done ? (
        <Alert variant="success">
          Invitation accepted. Switch to that business from the top bar. The assigned role cannot be changed here.
        </Alert>
      ) : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Input label="Invitation token" name="token" value={token} onChange={(e) => setToken(e.target.value)} />
      <Button type="submit" disabled={!token}>
        Accept invitation
      </Button>
    </form>
  );
}

export default function AcceptInvitationPage() {
  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold text-primary">Accept invitation</h1>
      <p className="text-sm text-muted-foreground">
        Sign in with the invited email, then submit the invitation token. You join with the role chosen by the inviter.
      </p>
      <Suspense>
        <AcceptInvitationForm />
      </Suspense>
      <p className="text-sm text-muted-foreground">
        After accepting, open <a className="text-secondary hover:underline" href={ROUTES.members}>Members</a> to see
        your membership.
      </p>
    </div>
  );
}
