import { AuthShell } from "@/components/auth/AuthShell";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { Suspense } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

export default function RegisterPage() {
  return (
    <AuthShell scene="dock" compact>
      <Suspense fallback={<LoadingEntity entity="form" compact />}>
        <RegisterForm />
      </Suspense>
    </AuthShell>
  );
}
