import { AuthShell } from "@/components/auth/AuthShell";
import { VerificationSuccess } from "@/components/auth/VerificationSuccess";

export default async function VerifyEmailSuccessPage({
  searchParams,
}: {
  searchParams: Promise<{ email?: string }>;
}) {
  const params = await searchParams;
  return (
    <AuthShell scene="celebrate" plain>
      <VerificationSuccess email={params.email ?? null} />
    </AuthShell>
  );
}
