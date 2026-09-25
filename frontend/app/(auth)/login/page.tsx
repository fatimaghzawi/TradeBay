import { AuthShell } from "@/components/auth/AuthShell";
import { LoginForm } from "@/components/auth/LoginForm";
import { Suspense } from "react";
import { LoadingEntity } from "@/components/ui/LoadingState";

export default function LoginPage() {
  return (
    <AuthShell scene="harbor">
      <Suspense fallback={<LoadingEntity entity="form" compact />}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
