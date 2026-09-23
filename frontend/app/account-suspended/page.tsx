import { AuthShell } from "@/components/auth/AuthShell";
import { ROUTES } from "@/lib/constants";
import Link from "next/link";

export default function AccountSuspendedPage() {
  return (
    <AuthShell variant="centered" plain>
      <div className="w-full max-w-md space-y-5 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[#fef3f2] text-xl font-bold text-[#b42318]">
          !
        </div>
        <div>
          <h1 className="font-[family-name:var(--font-outfit)] text-2xl font-bold text-[#0d3b2a]">
            Account suspended
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-[#5a6a62]">
            This TradeBay account has been suspended and cannot sign in. Sessions
            were revoked when the suspension was applied.
          </p>
        </div>
        <div className="border border-[#d4e0da] bg-white p-4 text-left text-sm text-[#4a5f55]">
          <p className="font-semibold text-[#0c1612]">What this means</p>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            <li>Marketplace and workspace access are blocked.</li>
            <li>Invitations and team actions for this user are paused.</li>
            <li>
              Contact your business admin or TradeBay support if you believe this
              was a mistake.
            </li>
          </ul>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Link
            href={ROUTES.login}
            className="inline-flex h-11 items-center justify-center rounded-xl bg-[#0d3b2a] px-5 text-sm font-semibold text-white"
          >
            Back to sign in
          </Link>
          <Link
            href={ROUTES.home}
            className="inline-flex h-11 items-center justify-center rounded-xl border border-[#dce5e0] px-5 text-sm font-semibold text-[#5a6a62]"
          >
            TradeBay home
          </Link>
        </div>
      </div>
    </AuthShell>
  );
}
