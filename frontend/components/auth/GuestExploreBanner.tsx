"use client";

import { ROUTES } from "@/lib/constants";
import { useAuth } from "@/providers/AuthProvider";
import Link from "next/link";

/** Soft prompt for guests exploring marketplace features. */
export function GuestExploreBanner({
  action = "save your work across devices",
}: {
  action?: string;
}) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading || isAuthenticated) return null;

  return (
    <div className="tb-guest-banner mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[color-mix(in_srgb,#e86f2a_28%,transparent)] bg-[color-mix(in_srgb,#e86f2a_8%,white)] px-4 py-3">
      <p className="m-0 text-sm text-[#5a3a22]">
        Exploring as a guest. Sign in to {action}.
      </p>
      <div className="flex gap-2">
        <Link
          href={ROUTES.login}
          className="rounded-full border border-[#e86f2a]/40 px-3 py-1.5 text-xs font-bold text-[#9a4a12]"
        >
          Log in
        </Link>
        <Link
          href={ROUTES.register}
          className="rounded-full bg-[#e86f2a] px-3 py-1.5 text-xs font-bold text-white"
        >
          Get started
        </Link>
      </div>
    </div>
  );
}
