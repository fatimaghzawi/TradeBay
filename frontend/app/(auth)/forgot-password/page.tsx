import { AuthShell } from "@/components/auth/AuthShell";
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";

/** Forgot password — desk scene. */
export default function ForgotPasswordPage() {
  return (
    <AuthShell scene="desk">
      <ForgotPasswordForm />
    </AuthShell>
  );
}
