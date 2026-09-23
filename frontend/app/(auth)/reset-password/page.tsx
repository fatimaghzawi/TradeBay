import { AuthShell } from "@/components/auth/AuthShell";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";
import { Suspense } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

/** Reset password — desk scene with stepper in the form. */
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
