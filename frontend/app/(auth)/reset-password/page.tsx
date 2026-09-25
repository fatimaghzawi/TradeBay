import { AuthShell } from "@/components/auth/AuthShell";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";
import { Suspense } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

export default function ResetPasswordPage() {
  return (
    <AuthShell scene="desk">
      <Suspense
        fallback={
          <LoadingEntity entity="reset form" />
        }
      >
        <ResetPasswordForm />
      </Suspense>
    </AuthShell>
  );
}
