"use client";

import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/authApi";
import { AUTH_QUERY_KEY } from "@/lib/auth/session";
import { loginSchema, type LoginFormValues } from "@/lib/validation/auth";
import { ROUTES } from "@/lib/constants";
import { useToast } from "@/components/ui/Toast";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

export function useLoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToast();
  const [errors, setErrors] = useState<Partial<Record<keyof LoginFormValues, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(values: LoginFormValues) {
    setFormError(null);
    const parsed = loginSchema.safeParse(values);
    if (!parsed.success) {
      const fieldErrors: Partial<Record<keyof LoginFormValues, string>> = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0];
        if (typeof key === "string") {
          fieldErrors[key as keyof LoginFormValues] = issue.message;
        }
      }
      setErrors(fieldErrors);
      return;
    }
    setErrors({});
    setPending(true);
    try {
      await authApi.login(parsed.data);
      await queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
      const me = await authApi.me().catch(() => null);
      const next = searchParams.get("next");
      const defaultHome =
        me?.active_business?.type === "platform" ? ROUTES.admin.home : ROUTES.dashboard;
      const safeNext =
        next && next.startsWith("/") && !next.startsWith("//") ? next : defaultHome;
      const joiningInvite =
        safeNext.includes(ROUTES.acceptInvitation) || safeNext.includes("accept-invitation");
      success(
        "Signed in",
        joiningInvite
          ? "Continue to accept or decline your invitation."
          : me?.active_business?.type === "platform"
            ? "Opening the platform command center."
            : "Welcome back to TradeBay.",
      );
      router.replace(safeNext);
    } catch (err) {
      if (err instanceof ApiError && err.code === "ACCOUNT_INACTIVE") {
        router.replace("/account-suspended");
        return;
      }
      const message =
        err instanceof ApiError ? err.message : "Couldn't sign in. Try again.";
      setFormError(message);
      toastError("Sign in failed", message);
    } finally {
      setPending(false);
    }
  }

  return { submit, errors, formError, pending };
}
