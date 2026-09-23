import { AuthShell } from "@/components/auth/AuthShell";
import { PasswordResetSuccess } from "@/components/auth/PasswordResetSuccess";

export default function ResetPasswordSuccessPage() {
  return (
    <AuthShell scene="celebrate" plain>
      <PasswordResetSuccess />
    </AuthShell>
  );
}
