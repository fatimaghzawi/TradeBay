import { AuthShell } from "@/components/auth/AuthShell";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { Suspense } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

/** Register — dock scene: warm orange wash, denser form. */
export default function RegisterPage() {
  return (
    <AuthShell scene="dock" compact>
      <Suspense fallback={<LoadingEntity entity="form" compact />}>
        <RegisterForm />
      </Suspense>
    </AuthShell>
  );
}
