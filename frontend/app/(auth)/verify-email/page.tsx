import { AuthShell } from "@/components/auth/AuthShell";
import { VerifyEmailForm } from "@/components/auth/VerifyEmailForm";
import { Suspense } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

/** Verify — coast scene: sunrise gradient stage. */
export default function VerifyEmailPage() {
  return (
    <AuthShell scene="coast">
      <Suspense
        fallback={
          <LoadingEntity entity="verification" />
        }
      >
        <VerifyEmailForm />
      </Suspense>
    </AuthShell>
  );
}
